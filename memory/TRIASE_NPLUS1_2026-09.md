# Triase kandidat N+1 (T-04 Langkah 1) — dihasilkan `scripts/triase_nplus1.py`

Total kandidat: **242** · BIARKAN (loop kecil): **3** · BIARKAN (sengaja): **7** · TIDAK TAHU: **232**

Vonis `PERBAIKI` hanya diberikan untuk lokasi yang sudah dibaca manusia (`VONIS_MANUAL`). `TIDAK TAHU` adalah vonis yang SAH — bukan tebakan. Tidak ada satu pun yang diperbaiki di langkah ini.

| # | Berkas:baris | Query | Loop (baris) atas | Vonis | Alasan |
|---|---|---|---|---|---|
| 1 | `backend/bootstrap.py:432` | `db.uoms.find_one` | `UOM_SEED_ROWS` (430) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 2 | `backend/bootstrap.py:575` | `db.products.find_one` | `enumerate(names)` (574) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 3 | `backend/bootstrap.py:741` | `db.cash_transactions.count_documents` | `receipts` (737) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 4 | `backend/bootstrap.py:772` | `db.purchase_requisitions.find` | `async for` (772) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 5 | `backend/bootstrap.py:857` | `db.purchase_orders.find` | `async for` (857) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 6 | `backend/bootstrap.py:975` | `db.hr_org_units.count_documents` | `entities` (973) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 7 | `backend/bootstrap.py:1002` | `db.hr_employees.find` | `async for` (1002) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 8 | `backend/bootstrap.py:1006` | `db.users.find` | `await db.users.find({"status": "active"}, {"_id": 0}).to_list(500)` (1006) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 9 | `backend/bootstrap.py:1012` | `db.hr_org_units.find_one` | `await db.users.find({"status": "active"}, {"_id": 0}).to_list(500)` (1006) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 10 | `backend/bootstrap.py:1074` | `db.hr_shifts.count_documents` | `entities` (1072) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 11 | `backend/bootstrap.py:1081` | `db.hr_geofences.count_documents` | `entities` (1072) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 12 | `backend/bootstrap.py:1096` | `db.hr_employees.find` | `entities` (1090) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 13 | `backend/bootstrap.py:1103` | `db.hr_employees.find` | `entities` (1090) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 14 | `backend/bootstrap.py:1092` | `db.hr_shifts.find_one` | `entities` (1090) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 15 | `backend/bootstrap.py:1228` | `db.hr_leave_balances.find_one` | `emps` (1227) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 16 | `backend/bootstrap.py:1599` | `db.users.find_one` | `({"id": "user_md_01", "name": "Rina Merchandiser", "email": "md@kainnu` (1590) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 17 | `backend/routers/admin.py:229` | `db.customers.find_one` | `enumerate(rows)` (219) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 18 | `backend/routers/admin.py:289` | `db.warehouses.find_one` | `enumerate(rows)` (282) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 19 | `backend/routers/admin.py:295` | `db.warehouses.find_one` | `enumerate(rows)` (282) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 20 | `backend/routers/categories.py:50` | `db.products.count_documents` | `rows` (48) | BIARKAN (loop kecil) | atas `rows` kategori master (puluhan baris); count per kategori — bisa jadi satu aggregate, tapi bukan jalur panas |
| 21 | `backend/routers/categories.py:77` | `db.design_gallery.find` | `async for` (77) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 22 | `backend/routers/contra_bons.py:160` | `db.wms_tasks.find` | `dec.get("bills", [])` (157) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 23 | `backend/routers/cycle_count.py:212` | `db.inventory_balances.find_one` | `session.get("items", [])` (211) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 24 | `backend/routers/entities.py:70` | `db.users.count_documents` | `rows` (68) | BIARKAN (loop kecil) | atas `rows` badan usaha (≤ puluhan, berhalaman `limit`); count user per entitas |
| 25 | `backend/routers/hr_attendance.py:473` | `db.hr_employees.find_one` | `parsed` (470) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 26 | `backend/routers/hr_tracking.py:48` | `db.hr_field_tracks.aggregate` | `async for` (48) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 27 | `backend/routers/purchase_orders.py:151` | `db.wms_tasks.find_one` | `po.get("items", [])` (149) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 28 | `backend/routers/reporting.py:207` | `db.inventory_balances.find` | `warehouses` (199) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 29 | `backend/routers/reporting.py:213` | `db.products.find` | `warehouses` (199) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 30 | `backend/routers/sales_orders.py:192` | `db.special_orders.find_one` | `payload.items` (168) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 31 | `backend/routers/sales_orders_extra.py:246` | `db.sales_orders.aggregate` | `(("7d", 7), ("30d", 30), ("90d", 90))` (244) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 32 | `backend/routers/sales_orders_extra.py:581` | `db.inventory_rolls.find_one` | `payload.roll_lines` (577) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 33 | `backend/routers/special_orders.py:141` | `db.special_orders.aggregate` | `async for` (141) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 34 | `backend/routers/transfers.py:198` | `db.products.find_one` | `payload.items` (197) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 35 | `backend/routers/transfers.py:300` | `db.products.find_one` | `payload.items` (299) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 36 | `backend/services/advance_report_service.py:80` | `db.customers.find` | `async for` (80) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 37 | `backend/services/approval_matrix_service.py:382` | `db.md_specs.find` | `await db.md_specs.find({**base, "status": "review"}, {"_id": 0} ).sort` (382) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 38 | `backend/services/approval_matrix_service.py:414` | `db.purchase_requisitions.find` | `await db.purchase_requisitions.find( {**base, "status": "pending_appro` (414) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 39 | `backend/services/approval_matrix_service.py:426` | `db.special_orders.find` | `await db.special_orders.find({**base, "status": "pending_approval"}, {` (426) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 40 | `backend/services/ar_aging_service.py:124` | `db.users.find` | `await db.users.find({"id": {"$in": list(sales_ids)}}, {"_id": 0, "id":` (124) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 41 | `backend/services/ar_aging_service.py:270` | `db.business_entities.find` | `async for` (270) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 42 | `backend/services/ar_receipt_service.py:310` | `db.sales_orders.find_one` | `applied` (304) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 43 | `backend/services/ar_receipt_service.py:575` | `db.sales_orders.find_one` | `r.get("allocations") or []` (573) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 44 | `backend/services/atp_policy.py:54` | `db.sales_orders.find` | `async for` (54) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 45 | `backend/services/bank_recon_service.py:205` | `db.bank_statement_formats.find_one` | `parser.BUILTIN_FORMATS` (204) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 46 | `backend/services/bank_recon_service.py:587` | `db.cash_transactions.find_one` | `allocations` (586) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 47 | `backend/services/bank_recon_service.py:603` | `db.cash_transactions.find_one` | `line.get("allocations") or []` (602) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 48 | `backend/services/bank_recon_service.py:667` | `db.bank_statement_lines.find_one` | `sorted(lines, key=lambda x: (x.get("stmt_date") or "", -_round(x.get("` (639) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 49 | `backend/services/bank_recon_service.py:749` | `db.cash_transactions.find_one` | `allocations` (745) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 50 | `backend/services/bank_recon_service.py:1140` | `db.sales_orders.find_one` | `allocations` (1131) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 51 | `backend/services/bank_recon_service.py:1333` | `db.cash_transactions.find` | `await db.cash_transactions.find( _book_query(acc, entity_ids), {"_id":` (1333) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 52 | `backend/services/bank_recon_service.py:1308` | `db.cash_transactions.find` | `await db.cash_transactions.find({"id": {"$in": tids}}, {"_id": 0}).to_` (1308) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 53 | `backend/services/budget_service.py:244` | `db.journal_entries.find` | `async for` (244) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 54 | `backend/services/budget_service.py:263` | `db.cash_advance_settlements.find` | `async for` (263) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 55 | `backend/services/budget_service.py:301` | `db.purchase_orders.find` | `async for` (301) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 56 | `backend/services/budget_service.py:315` | `db.cash_advance_settlements.find` | `async for` (315) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 57 | `backend/services/cash_entity_service.py:83` | `db.cash_transactions.find` | `async for` (83) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 58 | `backend/services/closing_service.py:184` | `db.journal_entries.find` | `async for` (184) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 59 | `backend/services/color_service.py:73` | `db.md_samples.find` | `async for` (73) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 60 | `backend/services/color_service.py:237` | `db.md_samples.find` | `cols` (234) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 61 | `backend/services/config_impact_service.py:202` | `db.sales_orders.find_one` | `plan["editable_documents"]` (199) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 62 | `backend/services/config_impact_service.py:236` | `db.sales_orders.find_one` | `before.items()` (233) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 63 | `backend/services/consolidation_service.py:462` | `db.journal_entries.find_one` | `seller_docs` (458) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 64 | `backend/services/consolidation_service.py:470` | `db.journal_entries.find_one` | `seller_docs` (458) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 65 | `backend/services/consolidation_service.py:731` | `db.interco_transactions.count_documents` | `by_pair.items()` (728) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 66 | `backend/services/contra_bon_reminder.py:136` | `db.suppliers.find` | `async for` (136) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 67 | `backend/services/contra_bon_reminder.py:179` | `db.suppliers.find` | `async for` (179) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 68 | `backend/services/contra_bon_scan.py:52` | `db.vendor_bills.find_one` | `per_bill.items()` (51) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 69 | `backend/services/contra_bon_scan.py:111` | `db.vendor_bills.find_one` | `async for` (102) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 70 | `backend/services/contra_bon_scan.py:178` | `db.purchase_returns.find_one` | `await _live_contra_bons()` (172) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 71 | `backend/services/contra_bon_scan.py:182` | `db.cash_transactions.find_one` | `await _live_contra_bons()` (172) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 72 | `backend/services/contra_bon_scan.py:224` | `db.journal_entries.find_one` | `async for` (219) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 73 | `backend/services/contra_bon_service.py:399` | `db.purchase_returns.find` | `async for` (399) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 74 | `backend/services/contra_bon_service.py:485` | `db.wms_tasks.find_one` | `pos` (461) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 75 | `backend/services/contra_bon_service.py:628` | `db.vendor_bills.find_one` | `picks` (625) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 76 | `backend/services/contra_bon_service.py:929` | `db.vendor_bills.find_one` | `cb.get("bills", [])` (928) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 77 | `backend/services/contra_bon_service.py:1118` | `db.vendor_bills.find_one` | `cb.get("bills", [])` (1098) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 78 | `backend/services/contra_bon_service.py:1129` | `db.vendor_bills.find_one_and_update` | `cb.get("bills", [])` (1098) | BIARKAN (sengaja) | find_one_and_update per dokumen = pengaman balapan (INV-CONC-01); JANGAN jadi bulk |
| 79 | `backend/services/contra_bon_service.py:421` | `db.cash_transactions.find` | `async for` (421) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 80 | `backend/services/customer_service.py:99` | `db.users.find_one` | `team or []` (96) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 81 | `backend/services/cycle_count_service.py:69` | `db.rfid_tags.find_one` | `extra_epcs` (68) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 82 | `backend/services/cycle_count_service.py:73` | `db.inventory_rolls.find_one` | `extra_epcs` (68) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 83 | `backend/services/cycle_count_service.py:75` | `db.warehouses.find_one` | `extra_epcs` (68) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 84 | `backend/services/data_hygiene_service.py:123` | `db.data_hygiene_log.aggregate` | `async for` (123) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 85 | `backend/services/design_gallery_service.py:51` | `db.design_gallery.find` | `async for` (51) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 86 | `backend/services/design_request_service.py:148` | `db.users.find` | `async for` (148) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 87 | `backend/services/design_request_service.py:155` | `db.rnd_person_divisions.find` | `async for` (155) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 88 | `backend/services/design_request_service.py:632` | `db.design_gallery.find` | `async for` (632) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 89 | `backend/services/design_request_service.py:224` | `db.design_gallery.find` | `async for` (224) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 90 | `backend/services/design_request_service.py:742` | `db.design_gallery.find` | `async for` (742) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 91 | `backend/services/design_studio_service.py:173` | `db.design_gallery.find` | `async for` (173) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 92 | `backend/services/design_studio_service.py:222` | `db.color_library.find_one` | `items or []` (218) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 93 | `backend/services/design_studio_service.py:235` | `db.products.find_one` | `ids or []` (234) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 94 | `backend/services/design_studio_service.py:525` | `db.md_samples.find` | `async for` (525) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 95 | `backend/services/design_studio_service.py:532` | `db.md_specs.find` | `async for` (532) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 96 | `backend/services/design_studio_service.py:206` | `db.design_gallery.find` | `async for` (206) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 97 | `backend/services/design_studio_service.py:541` | `db.products.find` | `async for` (541) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 98 | `backend/services/digest_service.py:176` | `db.sys_wa_outbox.find_one` | `recipients` (174) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 99 | `backend/services/doc_refs_service.py:644` | `db.landed_cost_vouchers.find` | `async for` (644) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 100 | `backend/services/doc_refs_service.py:652` | `db.ar_receipts.find` | `async for` (652) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 101 | `backend/services/entity_context_service.py:135` | `db.business_entities.find` | `async for` (135) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 102 | `backend/services/entity_context_service.py:152` | `db.users.find` | `async for` (152) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 103 | `backend/services/entity_lifecycle_service.py:196` | `db.business_entities.find` | `async for` (196) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 104 | `backend/services/finance_case_actions.py:269` | `db.bank_accounts.find_one` | `(from_acc, to_acc)` (268) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 105 | `backend/services/finance_case_actions.py:392` | `db.journal_entries.find_one` | `[c.get("id") for c in (rec.get("cash_transactions") or [])] + \ [rec.g` (388) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 106 | `backend/services/finance_case_actions.py:409` | `db.sales_orders.find_one` | `order_ids` (408) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 107 | `backend/services/finance_case_scan.py:246` | `db.journal_entries.find_one` | `async for` (234) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 108 | `backend/services/fixed_asset_service.py:221` | `db.fin_depreciation_entries.find_one` | `assets` (206) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 109 | `backend/services/fixed_asset_service.py:227` | `db.fin_fixed_assets.find_one_and_update` | `assets` (206) | BIARKAN (sengaja) | find_one_and_update per dokumen = pengaman balapan (INV-CONC-01); JANGAN jadi bulk |
| 110 | `backend/services/fleet_service.py:118` | `db.logistics_deliveries.find` | `async for` (118) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 111 | `backend/services/fulfillment_wizard_service.py:20` | `db.inventory_balances.find` | `async for` (20) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 112 | `backend/services/gl_service.py:763` | `db.journal_entries.find` | `async for` (763) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 113 | `backend/services/gl_service.py:1272` | `db.journal_entries.find` | `async for` (1272) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 114 | `backend/services/gl_service.py:1367` | `db.journal_entries.find_one` | `entries` (1363) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 115 | `backend/services/gl_service.py:1809` | `db.journal_entries.find` | `async for` (1809) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 116 | `backend/services/gl_service.py:2032` | `db.journal_entries.find` | `async for` (2032) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 117 | `backend/services/gl_service.py:2046` | `db.journal_entries.find` | `async for` (2046) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 118 | `backend/services/gl_service.py:2434` | `db.sales_orders.find_one` | `adv_orders` (2433) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 119 | `backend/services/gl_service.py:2495` | `db.sales_orders.find` | `async for` (2495) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 120 | `backend/services/gl_service.py:2871` | `db.inventory_rolls.find` | `ents` (2870) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 121 | `backend/services/gl_service.py:2964` | `db.journal_entries.find` | `async for` (2964) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 122 | `backend/services/gl_service.py:3155` | `db.journal_entries.count_documents` | `recon["rows"]` (3149) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 123 | `backend/services/group_partner_service.py:127` | `db.suppliers.find_one` | `active` (122) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 124 | `backend/services/group_partner_service.py:170` | `db.suppliers.find` | `async for` (170) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 125 | `backend/services/hr_leave_service.py:97` | `db.hr_leave_requests.find` | `async for` (97) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 126 | `backend/services/interco_money_service.py:80` | `db.cash_transactions.find_one` | `(("out", out_entity), ("in", in_entity))` (79) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 127 | `backend/services/interco_money_service.py:184` | `db.gl_accounts.find` | `async for` (184) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 128 | `backend/services/interco_service.py:1294` | `db.journal_entries.find_one` | `("seller", "cogs", "buyer", "receipt")` (1292) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 129 | `backend/services/interco_service.py:1347` | `db.journal_entries.find_one` | `settlements` (1345) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 130 | `backend/services/interco_service.py:1375` | `db.journal_entries.find_one` | `sorted(seen_rp)` (1373) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 131 | `backend/services/internal_request_service.py:91` | `db.inventory_balances.find` | `async for` (91) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 132 | `backend/services/landed_cost_service.py:158` | `db.inventory_rolls.find_one` | `allocations` (155) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 133 | `backend/services/line_scope.py:351` | `db.products.find` | `async for` (351) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 134 | `backend/services/line_scope.py:419` | `db.md_specs.find` | `async for` (419) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 135 | `backend/services/line_scope.py:422` | `db.md_samples.find` | `async for` (422) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 136 | `backend/services/location_service.py:52` | `db.inventory_rolls.find` | `async for` (52) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 137 | `backend/services/logistics_service.py:84` | `db.sales_orders.find_one` | `rows` (83) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 138 | `backend/services/lot_migration.py:48` | `db.products.find_one` | `groups.items()` (45) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 139 | `backend/services/lot_trace_service.py:107` | `db.wms_tasks.find_one` | `nodes` (100) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 140 | `backend/services/lot_trace_service.py:113` | `db.purchase_orders.find_one` | `nodes` (100) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 141 | `backend/services/lot_trace_service.py:118` | `db.makloon_orders.find_one` | `nodes` (100) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 142 | `backend/services/lot_trace_service.py:123` | `db.mfg_work_orders.find_one` | `nodes` (100) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 143 | `backend/services/makloon_order_service.py:253` | `db.process_recipes.find_one` | `enumerate(steps_in, start=1)` (249) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 144 | `backend/services/makloon_order_service.py:354` | `db.products.find_one` | `enumerate(steps_in, start=1)` (249) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 145 | `backend/services/makloon_order_service.py:355` | `db.products.find_one` | `enumerate(steps_in, start=1)` (249) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 146 | `backend/services/marketing_ext.py:67` | `db.mkt_posts.count_documents` | `rows` (65) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 147 | `backend/services/marketing_service.py:105` | `db.mkt_posts.aggregate` | `rows` (104) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 148 | `backend/services/notification_service.py:429` | `db.sales_orders.find_one` | `order_ids` (428) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 149 | `backend/services/notification_service.py:440` | `db.users.find_one` | `order_ids` (428) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 150 | `backend/services/payment_plan_service.py:409` | `db.ar_receipts.find` | `async for` (409) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 151 | `backend/services/payment_variance_service.py:225` | `db.sales_orders.find_one` | `wanted` (221) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 152 | `backend/services/payment_variance_service.py:414` | `db.sales_orders.find_one` | `order_ids` (411) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 153 | `backend/services/payment_variance_service.py:431` | `db.sales_orders.find_one_and_update` | `order_ids` (411) | BIARKAN (sengaja) | find_one_and_update per dokumen = pengaman balapan (INV-CONC-01); JANGAN jadi bulk |
| 154 | `backend/services/payment_variance_service.py:1166` | `db.ar_receipts.find` | `async for` (1166) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 155 | `backend/services/payment_variance_service.py:1219` | `db.ar_receipts.find` | `async for` (1219) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 156 | `backend/services/payment_variance_service.py:1241` | `db.ar_receipts.find_one` | `async for` (1238) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 157 | `backend/services/payment_variance_service.py:833` | `db.sales_orders.find_one` | `d.get("orders") or []` (829) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 158 | `backend/services/payment_variance_service.py:861` | `db.sales_orders.find_one` | `d.get("orders") or []` (857) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 159 | `backend/services/penalty_service.py:297` | `db.sales_orders.find` | `async for` (297) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 160 | `backend/services/penalty_service.py:559` | `db.journal_entries.find_one` | `async for` (558) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 161 | `backend/services/period_unlock_service.py:123` | `db.period_closings.find` | `async for` (123) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 162 | `backend/services/po_board_service.py:432` | `db.wms_tasks.find` | `async for` (432) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 163 | `backend/services/po_board_service.py:438` | `db.inventory_rolls.find` | `async for` (438) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 164 | `backend/services/po_board_service.py:448` | `db.products.find` | `async for` (448) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 165 | `backend/services/po_board_service.py:457` | `db.sales_orders.find` | `async for` (457) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 166 | `backend/services/pr_sourcing_service.py:374` | `db.products.find_one` | `lines` (373) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 167 | `backend/services/product_template_service.py:174` | `db.product_templates.find` | `async for` (174) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 168 | `backend/services/product_variant_service.py:125` | `db.product_templates.find_one` | `others` (122) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 169 | `backend/services/product_variant_service.py:197` | `db.products.find` | `async for` (197) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 170 | `backend/services/product_variant_service.py:223` | `db.inventory_rolls.count_documents` | `variants` (217) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 171 | `backend/services/product_variant_service.py:219` | `db.inventory_balances.find` | `variants` (217) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 172 | `backend/services/purchase_requisition_service.py:369` | `db.inventory_balances.find` | `async for` (369) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 173 | `backend/services/purchase_requisition_service.py:377` | `db.purchase_orders.find` | `async for` (377) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 174 | `backend/services/purchase_requisition_service.py:392` | `db.purchase_requisitions.find` | `async for` (392) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 175 | `backend/services/purchase_return_service.py:98` | `db.inventory_rolls.find` | `payload.items` (86) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 176 | `backend/services/purchase_return_service.py:391` | `db.inventory_rolls.find_one` | `ret.get("items", [])` (389) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 177 | `backend/services/purchase_return_service.py:463` | `db.inventory_rolls.find_one` | `ret.get("items", [])` (461) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 178 | `backend/services/purchase_return_service.py:762` | `db.inventory_rolls.find_one` | `{m.get("roll_id") for m in movements if m.get("roll_id")}` (761) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 179 | `backend/services/purchase_return_service.py:220` | `db.interco_returns.find_one` | `pairs` (218) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 180 | `backend/services/purchase_return_service.py:565` | `db.purchase_orders.find_one` | `{r.get("product_id") for r in rolls}` (564) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 181 | `backend/services/putaway_order_service.py:106` | `db.rfid_tags.find_one` | `rolls` (96) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 182 | `backend/services/restock_service.py:207` | `db.products.find_one` | `raw` (188) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 183 | `backend/services/return_service.py:67` | `db.wms_tasks.find` | `async for` (67) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 184 | `backend/services/return_service.py:92` | `db.products.find_one` | `items or []` (89) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 185 | `backend/services/return_service.py:108` | `db.sales_returns.find` | `async for` (108) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 186 | `backend/services/return_service.py:823` | `db.products.find_one` | `items` (794) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 187 | `backend/services/return_service.py:989` | `db.journal_entries.find_one` | `q_rolls` (937) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 188 | `backend/services/return_service.py:1600` | `db.warehouses.find_one` | `from_ids` (1599) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 189 | `backend/services/rfid_incident_service.py:119` | `db.rfid_reads.aggregate` | `async for` (119) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 190 | `backend/services/rfid_incident_service.py:124` | `db.rfid_incidents.aggregate` | `async for` (124) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 191 | `backend/services/rfid_incident_service.py:132` | `db.inventory_rolls.aggregate` | `async for` (132) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 192 | `backend/services/rfid_ingest_service.py:99` | `db.rfid_tags.find_one` | `list(dict.fromkeys(e.strip().upper() for e in epcs if e and e.strip())` (98) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 193 | `backend/services/rfid_ingest_service.py:100` | `db.inventory_rolls.find_one` | `list(dict.fromkeys(e.strip().upper() for e in epcs if e and e.strip())` (98) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 194 | `backend/services/rfid_print_service.py:130` | `db.rfid_tags.find_one` | `rolls` (121) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 195 | `backend/services/rfid_service.py:259` | `db.rfid_devices.find_one` | `whs` (251) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 196 | `backend/services/rfid_service.py:342` | `db.inventory_rolls.find_one` | `tags` (341) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 197 | `backend/services/rfq_service.py:67` | `db.suppliers.find_one` | `supplier_ids` (63) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 198 | `backend/services/rfq_service.py:342` | `db.suppliers.find_one` | `grouped.items()` (336) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 199 | `backend/services/rnd_kpi_service.py:74` | `db.users.find` | `async for` (74) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 200 | `backend/services/rnd_org_service.py:27` | `db.users.find` | `async for` (27) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 201 | `backend/services/roll_service.py:87` | `db.inventory_rolls.find_one` | `range(200)` (85) | BIARKAN (loop kecil) | loop terbatas `range` |
| 202 | `backend/services/roll_service.py:315` | `db.inventory_rolls.find` | `balances` (312) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 203 | `backend/services/roll_service.py:1123` | `db.inventory_rolls.find_one_and_update` | `rolls` (1118) | BIARKAN (sengaja) | find_one_and_update per dokumen = pengaman balapan (INV-CONC-01); JANGAN jadi bulk |
| 204 | `backend/services/roll_service.py:1370` | `db.inventory_rolls.find_one_and_update` | `rolls` (1365) | BIARKAN (sengaja) | find_one_and_update per dokumen = pengaman balapan (INV-CONC-01); JANGAN jadi bulk |
| 205 | `backend/services/roll_service.py:59` | `db.inventory_rolls.find` | `async for` (59) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 206 | `backend/services/roll_service.py:1764` | `db.inventory_rolls.find_one` | `roll_lines or []` (1759) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 207 | `backend/services/roll_service.py:1779` | `db.inventory_rolls.find_one_and_update` | `roll_lines or []` (1759) | BIARKAN (sengaja) | find_one_and_update per dokumen = pengaman balapan (INV-CONC-01); JANGAN jadi bulk |
| 208 | `backend/services/roll_service.py:1790` | `db.inventory_rolls.find_one_and_update` | `roll_lines or []` (1759) | BIARKAN (sengaja) | find_one_and_update per dokumen = pengaman balapan (INV-CONC-01); JANGAN jadi bulk |
| 209 | `backend/services/roll_timeline_service.py:50` | `db.rfid_print_jobs.find` | `async for` (50) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 210 | `backend/services/roll_timeline_service.py:63` | `db.putaway_orders.find` | `async for` (63) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 211 | `backend/services/roll_timeline_service.py:83` | `db.inventory_movements.find` | `async for` (83) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 212 | `backend/services/roll_timeline_service.py:99` | `db.roll_scans.find` | `async for` (99) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 213 | `backend/services/roll_timeline_service.py:93` | `db.rfid_reads.find` | `async for` (93) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 214 | `backend/services/sales_order_helpers.py:90` | `db.inventory_rolls.find_one` | `roll_lines or []` (87) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 215 | `backend/services/scheduler_service.py:270` | `db.sys_scheduler_runs.find_one` | `JOBS` (269) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 216 | `backend/services/so_approvals.py:138` | `db.sales_orders.find` | `async for` (138) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 217 | `backend/services/so_verify_service.py:180` | `db.inventory_balances.find` | `async for` (180) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 218 | `backend/services/store_credit_service.py:57` | `db.store_credit_ledger.find` | `async for` (57) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 219 | `backend/services/store_credit_service.py:66` | `db.store_credit_ledger.find` | `async for` (66) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 220 | `backend/services/store_credit_service.py:98` | `db.store_credit_ledger.aggregate` | `async for` (98) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 221 | `backend/services/store_credit_service.py:297` | `db.credit_notes.find` | `async for` (297) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 222 | `backend/services/store_credit_service.py:301` | `db.store_credit_ledger.find_one` | `async for` (297) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 223 | `backend/services/store_credit_service.py:306` | `db.journal_entries.find_one` | `async for` (297) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 224 | `backend/services/store_credit_service.py:205` | `db.sales_orders.find_one` | `allocations` (201) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 225 | `backend/services/tax_center_service.py:62` | `db.sales_orders.find` | `async for` (62) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 226 | `backend/services/tracking_service.py:104` | `db.hr_field_tracks.aggregate` | `async for` (104) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 227 | `backend/services/turn_notification_service.py:97` | `db.users.find_one` | `OWNER_FIELDS` (93) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 228 | `backend/services/vendor_bill_service.py:35` | `db.vendor_bills.find` | `async for` (35) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 229 | `backend/services/vendor_bill_service.py:185` | `db.vendor_bills.find` | `async for` (185) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 230 | `backend/services/wa_alert_service.py:196` | `db.sys_wa_outbox.find_one` | `recipients` (194) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 231 | `backend/services/warehouse_profile_service.py:77` | `db.warehouses.find` | `async for` (77) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 232 | `backend/services/warehouse_profile_service.py:150` | `db.warehouse_sites.find_one` | `BLUEPRINT_SITES` (149) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 233 | `backend/services/warehouse_profile_service.py:162` | `db.warehouses.find_one` | `BLUEPRINT_WH` (161) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 234 | `backend/services/wms_health_service.py:29` | `db.rfid_incidents.aggregate` | `async for` (29) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 235 | `backend/services/wms_health_service.py:34` | `db.rfid_reads.aggregate` | `async for` (34) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 236 | `backend/services/wms_health_service.py:40` | `db.inventory_rolls.aggregate` | `async for` (40) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 237 | `backend/services/wms_health_service.py:46` | `db.putaway_orders.aggregate` | `async for` (46) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 238 | `backend/services/wms_health_service.py:52` | `db.inventory_rolls.aggregate` | `async for` (52) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 239 | `backend/services/wms_health_service.py:58` | `db.inventory_rolls.aggregate` | `async for` (58) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 240 | `backend/services/wms_health_service.py:66` | `db.rfid_cycle_counts.aggregate` | `async for` (66) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 241 | `backend/services/wms_health_service.py:76` | `db.rfid_devices.find` | `async for` (76) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |
| 242 | `backend/services/work_desk_service.py:307` | `db.tax_invoices.find` | `async for` (307) | TIDAK TAHU | ukuran iterabel tidak bisa disimpulkan statik — belum dibaca manusia |

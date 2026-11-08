# B3a — Lampiran: Profil field koleksi WMS-RFID (data kn_test_trial) + pemakaian field di kode

Dibangkitkan: `scripts/audit/b3a_field_profile.js` (≤ 50.000 dok per koleksi; `inventory_movements` = 50.000 dari 85.363) → `scripts/audit/b3a_profile_md.py`; pemakaian: `scripts/audit/b3a_field_usage.py`.

* **ada %** = dokumen yang memiliki path; **terisi %** = bukan null/""/[]/{}. Path ≤ 1 titik (detail lebih dalam di keluaran JSON skrip).
* Pemakaian: jumlah SEBUTAN nama field (kata utuh) di backend app & `frontend/src`; kelas `TULIS_TANPA_BACA` = hanya disebut oleh penulisnya (kandidat — bisa dibaca lewat objek utuh di FE).

## A. Pemakaian field tingkat atas di kode

### inventory_rolls (46700 dok)
| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |
|---|---:|---:|---:|---:|---|
| `acquired` | 46700 | 71 | 7 | 6 |  |
| `acquired_history` | 12 | 22 | 0 | 2 |  |
| `actual_task_qty` | 10 | 17 | 3 | 1 |  |
| `base_unit_cost` | 46700 | 94 | 3 | 13 |  |
| `batch` | 46688 | 162 | 67 | 4 |  |
| `bin_code` | 2 | 36 | 17 | 5 |  |
| `bin_id` | 37220 | 277 | 53 | 10 |  |
| `bin_sim` | 37210 | 0 | 0 | 0 | DATA_TANPA_KODE |
| `bucket_ref` | 76 | 39 | 0 | 11 |  |
| `committed_to` | 0 | 6 | 0 | 2 |  |
| `condition` | 12 | 72 | 44 | 1 |  |
| `consignor_ref` | 0 | 6 | 0 | 4 |  |
| `consumed_ref` | 44 | 3 | 0 | 3 | TULIS_TANPA_BACA (kandidat) |
| `cost_backfilled_at` | 4 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `cost_basis` | 13 | 33 | 3 | 3 |  |
| `cost_missing` | 4 | 8 | 0 | 2 |  |
| `created_at` | 46700 | 1255 | 118 | 6 |  |
| `created_by` | 46688 | 566 | 57 | 4 |  |
| `created_by_name` | 46688 | 12 | 2 | 4 |  |
| `cut` | 40 | 94 | 76 | 2 |  |
| `declared_length` | 0 | 5 | 7 | 0 |  |
| `declared_task_qty` | 0 | 10 | 2 | 0 |  |
| `declared_weight_kg` | 0 | 5 | 8 | 0 |  |
| `defects` | 10 | 73 | 23 | 8 |  |
| `delivered_at` | 13 | 46 | 7 | 2 |  |
| `dye_lot` | 46700 | 213 | 91 | 7 |  |
| `earmarked_for` | 0 | 45 | 4 | 13 |  |
| `fabric_type` | 46700 | 197 | 84 | 0 |  |
| `four_point_pending` | 29 | 2 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `gate_exit` | 1 | 3 | 0 | 1 | JARANG |
| `grade` | 46700 | 754 | 469 | 14 |  |
| `grade_history` | 13 | 13 | 1 | 3 |  |
| `grade_source` | 52 | 9 | 7 | 1 |  |
| `grade_updated_at` | 52 | 5 | 0 | 1 |  |
| `grn_expected_seq` | 0 | 2 | 0 | 0 | JARANG |
| `grn_id` | 10 | 246 | 9 | 0 |  |
| `grn_line_no` | 10 | 9 | 1 | 0 |  |
| `grn_task_id` | 65 | 22 | 3 | 2 |  |
| `hold` | 10 | 244 | 161 | 2 |  |
| `hold_history` | 10 | 8 | 0 | 3 |  |
| `id` | 46700 | 9757 | 6977 | 6 |  |
| `inspected_4point` | 7 | 4 | 1 | 0 |  |
| `inspected_4point_at` | 7 | 1 | 0 | 0 | JARANG |
| `inspected_4point_by` | 7 | 1 | 0 | 0 | JARANG |
| `inspected_4point_spk` | 7 | 3 | 2 | 0 |  |
| `inspection` | 84 | 184 | 48 | 7 |  |
| `is_remnant` | 46688 | 22 | 0 | 5 |  |
| `is_sample_cut` | 17 | 1 | 0 | 0 | JARANG |
| `journey` | 135 | 91 | 69 | 11 |  |
| `label_variance` | 0 | 5 | 2 | 1 |  |
| `landed_cost_refs` | 0 | 10 | 0 | 5 |  |
| `landed_cost_total` | 46700 | 22 | 0 | 8 |  |
| `last_pa_landed` | 2 | 5 | 0 | 1 |  |
| `last_transfer` | 1 | 9 | 0 | 2 |  |
| `length` | 12 | 227 | 3358 | 3 |  |
| `length_initial` | 46700 | 83 | 7 | 22 |  |
| `length_remaining` | 46700 | 442 | 53 | 35 |  |
| `length_reservations` | 19 | 36 | 0 | 7 |  |
| `length_reserved` | 53 | 68 | 0 | 2 |  |
| `line_code` | 46659 | 219 | 38 | 0 |  |
| `location_type` | 46688 | 5 | 0 | 4 | TULIS_TANPA_BACA (kandidat) |
| `lot` | 46700 | 1073 | 701 | 9 |  |
| `lot_id` | 46700 | 184 | 4 | 7 |  |
| `md_quality_checked` | 33 | 5 | 1 | 0 |  |
| `md_quality_checked_at` | 33 | 1 | 0 | 0 | JARANG |
| `md_quality_checked_by` | 33 | 1 | 0 | 0 | JARANG |
| `md_quality_spk` | 33 | 3 | 1 | 0 |  |
| `measure_confirmed` | 10 | 5 | 4 | 1 |  |
| `opname_found_code` | 1 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `origin_ref` | 12 | 3 | 0 | 1 | JARANG |
| `origin_type` | 12 | 53 | 15 | 1 |  |
| `owner_entity_id` | 46700 | 848 | 59 | 5 |  |
| `ownership_type` | 46688 | 8 | 0 | 4 |  |
| `parent_roll_id` | 97 | 29 | 0 | 3 |  |
| `parent_roll_no` | 17 | 5 | 7 | 0 |  |
| `pending_cut_ops` | 0 | 7 | 0 | 2 |  |
| `po_id` | 65 | 467 | 49 | 2 |  |
| `po_number` | 65 | 324 | 144 | 2 |  |
| `product_id` | 46700 | 2598 | 690 | 6 |  |
| `qc_grade` | 40 | 8 | 3 | 1 |  |
| `qc_passed_at` | 40 | 3 | 0 | 0 | JARANG |
| `qc_rejected_at` | 12 | 4 | 0 | 0 |  |
| `qc_status` | 12 | 13 | 3 | 2 |  |
| `qc_task_id` | 17 | 17 | 0 | 3 |  |
| `qc_via_sampling` | 49 | 3 | 0 | 1 | JARANG |
| `random_check_id` | 4 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `received_date` | 65 | 15 | 0 | 2 |  |
| `regraded_from` | 1 | 7 | 2 | 1 |  |
| `reject_reason` | 12 | 48 | 24 | 0 |  |
| `reserved_ref` | 136 | 138 | 5 | 26 |  |
| `return_history` | 2 | 10 | 0 | 2 |  |
| `return_id` | 12 | 591 | 6 | 2 |  |
| `returned_from_customer_ids` | 2 | 4 | 0 | 2 |  |
| `returned_from_status` | 3 | 2 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `returned_ref` | 7 | 6 | 0 | 3 |  |
| `rfid_tag_id` | 38 | 86 | 0 | 11 |  |
| `roll_no` | 46700 | 587 | 194 | 10 |  |
| `root_roll_id` | 97 | 7 | 0 | 2 |  |
| `scan_source` | 10 | 8 | 1 | 0 |  |
| `secondary_measures` | 65 | 21 | 7 | 7 |  |
| `shipped_at` | 94 | 14 | 3 | 1 |  |
| `sim_anomaly` | 12 | 0 | 0 | 0 | DATA_TANPA_KODE |
| `source_roll_ids` | 2 | 2 | 0 | 0 | JARANG |
| `split_from_roll_id` | 2 | 1 | 0 | 0 | JARANG |
| `stage` | 46700 | 562 | 368 | 1 |  |
| `status` | 46700 | 6114 | 3268 | 63 |  |
| `supplier_color` | 7 | 34 | 22 | 1 |  |
| `supplier_dn_number` | 10 | 18 | 8 | 2 |  |
| `supplier_id` | 71 | 771 | 197 | 2 |  |
| `supplier_invoice_no` | 1 | 60 | 22 | 3 |  |
| `supplier_item_name` | 8 | 74 | 43 | 1 |  |
| `supplier_lot` | 10 | 120 | 51 | 4 |  |
| `supplier_name` | 71 | 389 | 183 | 2 |  |
| `supplier_return_ref` | 1 | 2 | 0 | 2 | TULIS_TANPA_BACA (kandidat) |
| `supplier_sku` | 8 | 153 | 62 | 1 |  |
| `tracking_mode` | 46688 | 13 | 0 | 7 |  |
| `transfer_prior_status` | 10 | 4 | 0 | 2 |  |
| `transfer_ref` | 10 | 21 | 0 | 5 |  |
| `unit` | 46700 | 1503 | 986 | 7 |  |
| `unit_cost` | 46684 | 191 | 19 | 13 |  |
| `updated_at` | 46700 | 1268 | 19 | 110 |  |
| `usage_history` | 0 | 2 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `vendor_bill_id` | 3 | 18 | 3 | 3 |  |
| `warehouse_id` | 46700 | 1552 | 224 | 12 |  |
| `weight_kg` | 65 | 129 | 35 | 5 |  |
| `weight_unit` | 65 | 3 | 0 | 3 | TULIS_TANPA_BACA (kandidat) |

### inventory_balances (393 dok)
| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |
|---|---:|---:|---:|---:|---|
| `atp_qty` | 393 | 5 | 5 | 1 |  |
| `available_qty` | 393 | 105 | 70 | 1 |  |
| `blocked_qty` | 393 | 15 | 2 | 1 |  |
| `committed_qty` | 393 | 6 | 2 | 0 |  |
| `damaged_qty` | 393 | 3 | 2 | 0 |  |
| `hold_qty` | 393 | 5 | 6 | 0 |  |
| `id` | 393 | 9757 | 6977 | 2 |  |
| `in_transit_inbound_qty` | 393 | 4 | 0 | 0 |  |
| `in_transit_intercompany_qty` | 393 | 2 | 0 | 0 | JARANG |
| `in_transit_qty` | 393 | 11 | 1 | 2 |  |
| `in_transit_sales_qty` | 393 | 2 | 0 | 0 | JARANG |
| `in_transit_transfer_qty` | 393 | 2 | 0 | 0 | JARANG |
| `incoming_qty` | 393 | 4 | 0 | 1 |  |
| `on_hand_qty` | 393 | 44 | 10 | 2 |  |
| `on_hand_roll_count` | 393 | 17 | 1 | 2 |  |
| `on_order_qty` | 393 | 2 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `owned_qty` | 393 | 4 | 0 | 1 |  |
| `owner_entity_id` | 393 | 848 | 59 | 3 |  |
| `packed_qty` | 393 | 2 | 1 | 0 | JARANG |
| `pending_demand_qty` | 393 | 4 | 0 | 1 |  |
| `picked_qty` | 393 | 48 | 22 | 1 |  |
| `product_id` | 393 | 2598 | 690 | 2 |  |
| `projection_valid` | 393 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `quarantine_qty` | 393 | 6 | 7 | 0 |  |
| `rebuild_applied` | 393 | 3 | 0 | 1 | JARANG |
| `rebuild_ticket` | 393 | 3 | 0 | 1 | JARANG |
| `reserved_qty` | 393 | 93 | 23 | 1 |  |
| `roll_count` | 393 | 109 | 28 | 2 |  |
| `roll_counts` | 393 | 12 | 0 | 2 |  |
| `subcon_qty` | 393 | 5 | 4 | 0 |  |
| `unconvertible_roll_count` | 393 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `updated_at` | 393 | 1268 | 19 | 2 |  |
| `warehouse_id` | 393 | 1552 | 224 | 2 |  |
| `wip_qty` | 393 | 3 | 6 | 0 |  |

### inventory_lots (462 dok)
| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |
|---|---:|---:|---:|---:|---|
| `active_roll_count` | 462 | 2 | 1 | 1 | JARANG |
| `child_lot_ids` | 4 | 11 | 1 | 1 |  |
| `created_at` | 462 | 1255 | 118 | 0 |  |
| `created_by` | 462 | 566 | 57 | 0 |  |
| `created_by_name` | 462 | 12 | 2 | 0 |  |
| `dye_lot` | 52 | 213 | 91 | 0 |  |
| `entity_id` | 462 | 5990 | 610 | 0 |  |
| `fabric_type` | 462 | 197 | 84 | 0 |  |
| `id` | 462 | 9757 | 6977 | 0 |  |
| `legacy_lot_codes` | 452 | 12 | 4 | 1 |  |
| `lot_number` | 462 | 78 | 35 | 0 |  |
| `lot_status` | 462 | 43 | 28 | 1 |  |
| `note` | 0 | 1486 | 902 | 0 |  |
| `owner_entity_id` | 462 | 848 | 59 | 0 |  |
| `parent_lot_ids` | 7 | 30 | 1 | 1 |  |
| `process` | 462 | 30 | 52 | 0 |  |
| `product_id` | 462 | 2598 | 690 | 0 |  |
| `product_name` | 462 | 505 | 308 | 0 |  |
| `qty_available` | 462 | 2 | 1 | 1 | JARANG |
| `qty_initial` | 462 | 2 | 1 | 1 | JARANG |
| `qty_remaining` | 462 | 29 | 19 | 1 |  |
| `roll_count` | 462 | 109 | 28 | 1 |  |
| `shade_ref` | 0 | 34 | 21 | 0 |  |
| `sku` | 462 | 1022 | 428 | 0 |  |
| `source` | 462 | 619 | 258 | 0 |  |
| `source_ref` | 462 | 104 | 11 | 0 |  |
| `stage` | 462 | 562 | 368 | 1 |  |
| `status_breakdown` | 428 | 2 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `status_history` | 462 | 43 | 6 | 1 |  |
| `supplier_dn_numbers` | 12 | 15 | 8 | 1 |  |
| `supplier_id` | 34 | 771 | 197 | 0 |  |
| `supplier_lot` | 9 | 120 | 51 | 0 |  |
| `supplier_name` | 34 | 389 | 183 | 0 |  |
| `unit` | 462 | 1503 | 986 | 0 |  |
| `updated_at` | 462 | 1268 | 19 | 5 |  |
| `warehouse_id` | 462 | 1552 | 224 | 0 |  |

### wms_tasks (252 dok)
| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |
|---|---:|---:|---:|---:|---|
| `allocation_id` | 120 | 9 | 0 | 3 |  |
| `assigned_to` | 2 | 55 | 22 | 1 |  |
| `assigned_to_name` | 2 | 3 | 2 | 1 |  |
| `batch` | 28 | 162 | 67 | 7 |  |
| `bin_id` | 32 | 277 | 53 | 9 |  |
| `cancel_reason` | 16 | 42 | 10 | 4 |  |
| `cancelled_by` | 16 | 29 | 7 | 2 |  |
| `child_roll_no` | 17 | 17 | 22 | 0 |  |
| `conversion_variance` | 33 | 5 | 0 | 0 |  |
| `created_at` | 252 | 1255 | 118 | 7 |  |
| `created_by` | 252 | 566 | 57 | 6 |  |
| `customer_name` | 20 | 419 | 191 | 1 |  |
| `cut_at` | 17 | 9 | 1 | 0 |  |
| `cut_by` | 17 | 2 | 0 | 0 | JARANG |
| `cutting_handoff` | 17 | 12 | 5 | 1 |  |
| `declared_grn_ids` | 8 | 2 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `declared_qty_total` | 8 | 3 | 0 | 1 | JARANG |
| `dye_lot` | 0 | 213 | 91 | 1 |  |
| `entity_id` | 252 | 5990 | 610 | 5 |  |
| `escalation` | 2 | 76 | 46 | 8 |  |
| `expected_grade` | 122 | 44 | 19 | 1 |  |
| `expected_qty` | 129 | 62 | 25 | 6 |  |
| `expected_rolls` | 2 | 21 | 35 | 2 |  |
| `flow_type` | 252 | 92 | 10 | 5 |  |
| `fulfillment_method` | 123 | 31 | 20 | 2 |  |
| `gl_posting` | 33 | 14 | 0 | 3 |  |
| `grade` | 26 | 754 | 469 | 1 |  |
| `grn_id` | 0 | 246 | 9 | 1 |  |
| `grn_ids` | 8 | 4 | 5 | 2 |  |
| `grn_number` | 0 | 14 | 9 | 1 |  |
| `hold_until` | 0 | 6 | 2 | 2 |  |
| `id` | 252 | 9757 | 6977 | 7 |  |
| `last_shipment_id` | 60 | 1 | 0 | 0 | JARANG |
| `line_code` | 2 | 219 | 38 | 2 |  |
| `line_product_id` | 20 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `lot` | 84 | 1073 | 701 | 7 |  |
| `lot_ids` | 35 | 38 | 1 | 2 |  |
| `lot_numbers` | 33 | 4 | 0 | 1 |  |
| `lot_warnings` | 25 | 8 | 3 | 1 |  |
| `makloon_id` | 2 | 101 | 40 | 1 |  |
| `mko_id` | 2 | 278 | 7 | 1 |  |
| `mko_number` | 2 | 92 | 19 | 1 |  |
| `needs_review` | 33 | 35 | 3 | 0 |  |
| `off_suggestion_reason` | 0 | 2 | 2 | 0 |  |
| `order_id` | 123 | 1471 | 176 | 2 |  |
| `order_number` | 123 | 184 | 87 | 2 |  |
| `order_type` | 20 | 42 | 9 | 1 |  |
| `over_receipt` | 34 | 6 | 0 | 1 |  |
| `over_receipt_note` | 0 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `owner_entity_id` | 2 | 848 | 59 | 3 |  |
| `parent_roll_id` | 17 | 29 | 0 | 0 |  |
| `parent_roll_no` | 17 | 5 | 7 | 0 |  |
| `picked_qty` | 123 | 48 | 22 | 4 |  |
| `po_id` | 127 | 467 | 49 | 2 |  |
| `po_number` | 127 | 324 | 144 | 2 |  |
| `product_id` | 252 | 2598 | 690 | 5 |  |
| `product_name` | 252 | 505 | 308 | 5 |  |
| `qc_accept_qty` | 22 | 1 | 0 | 0 | JARANG |
| `qc_at` | 22 | 9 | 1 | 0 |  |
| `qc_by` | 22 | 3 | 5 | 0 |  |
| `qc_coverage` | 22 | 9 | 0 | 0 |  |
| `qc_reason` | 22 | 1 | 0 | 0 | JARANG |
| `qc_reject_disposition` | 8 | 1 | 0 | 0 | JARANG |
| `qc_reject_qty` | 22 | 1 | 0 | 0 | JARANG |
| `qc_status` | 35 | 13 | 3 | 1 |  |
| `qty_rolls` | 35 | 154 | 54 | 5 |  |
| `qty_rolls_scanned` | 8 | 8 | 3 | 2 |  |
| `quantity` | 252 | 637 | 314 | 14 |  |
| `quarantine_qty` | 35 | 6 | 7 | 2 |  |
| `receipt_role` | 2 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `receive_mode` | 8 | 2 | 0 | 0 | JARANG |
| `receive_tolerance_percent` | 26 | 15 | 0 | 1 |  |
| `receive_variance_percent` | 26 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `receive_within_tolerance` | 34 | 3 | 0 | 1 | JARANG |
| `received_qty` | 129 | 134 | 39 | 7 |  |
| `refs` | 184 | 171 | 51 | 0 |  |
| `roll_id` | 82 | 1100 | 282 | 8 |  |
| `sample_billing` | 20 | 26 | 18 | 1 |  |
| `scan_log` | 99 | 26 | 4 | 12 |  |
| `shipped_qty` | 123 | 27 | 6 | 3 |  |
| `sku` | 252 | 1022 | 428 | 5 |  |
| `source_type` | 252 | 395 | 23 | 5 |  |
| `special_order_id` | 0 | 87 | 4 | 1 |  |
| `stages` | 252 | 98 | 35 | 5 |  |
| `status` | 252 | 6114 | 3268 | 23 |  |
| `step_seq` | 2 | 90 | 28 | 1 |  |
| `suggested_roll_id` | 18 | 7 | 5 | 1 |  |
| `suggested_roll_no` | 18 | 5 | 10 | 1 |  |
| `supplier_conv_factor` | 127 | 9 | 0 | 1 |  |
| `supplier_dn_missing` | 33 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `supplier_dn_number` | 9 | 18 | 8 | 1 |  |
| `supplier_dn_numbers` | 8 | 15 | 8 | 1 |  |
| `supplier_item_id` | 21 | 29 | 5 | 1 |  |
| `supplier_item_name` | 21 | 74 | 43 | 1 |  |
| `supplier_lot` | 8 | 120 | 51 | 2 |  |
| `supplier_name` | 129 | 389 | 183 | 2 |  |
| `supplier_sku` | 21 | 153 | 62 | 1 |  |
| `supplier_uom` | 8 | 44 | 21 | 1 |  |
| `takeover_log` | 2 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `task_subtype` | 22 | 12 | 13 | 2 |  |
| `unit` | 252 | 1503 | 986 | 6 |  |
| `unit_factor` | 0 | 26 | 15 | 1 |  |
| `unit_factor_to` | 0 | 20 | 7 | 1 |  |
| `uom_trail` | 33 | 26 | 1 | 0 |  |
| `updated_at` | 252 | 1268 | 19 | 36 |  |
| `warehouse_city` | 252 | 39 | 14 | 6 |  |
| `warehouse_id` | 252 | 1552 | 224 | 7 |  |
| `warehouse_name` | 252 | 165 | 119 | 6 |  |

### warehouse_transfers (17 dok)
| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |
|---|---:|---:|---:|---:|---|
| `approved_at` | 3 | 96 | 27 | 4 |  |
| `approved_by` | 3 | 116 | 28 | 4 |  |
| `code` | 17 | 2026 | 1113 | 4 |  |
| `completed_at` | 1 | 34 | 6 | 1 |  |
| `completion_basis` | 1 | 4 | 0 | 1 |  |
| `created_at` | 17 | 1255 | 118 | 4 |  |
| `dest_entity_id` | 15 | 47 | 3 | 4 |  |
| `dest_warehouse_id` | 17 | 32 | 9 | 4 |  |
| `entity_id` | 17 | 5990 | 610 | 4 |  |
| `id` | 17 | 9757 | 6977 | 4 |  |
| `interco_id` | 1 | 98 | 9 | 2 |  |
| `interco_number` | 1 | 12 | 2 | 2 |  |
| `interco_pair_id` | 1 | 42 | 0 | 3 |  |
| `items` | 17 | 2416 | 4841 | 5 |  |
| `je_intercompany` | 1 | 4 | 6 | 1 |  |
| `line_codes` | 17 | 22 | 0 | 1 |  |
| `linked_order_id` | 0 | 9 | 0 | 3 |  |
| `notes` | 17 | 638 | 438 | 4 |  |
| `ownership_moved` | 1 | 4 | 0 | 2 |  |
| `receipt_events` | 1 | 4 | 0 | 1 |  |
| `refs` | 0 | 171 | 51 | 0 |  |
| `rejected_at` | 3 | 37 | 8 | 3 |  |
| `rejected_by` | 3 | 51 | 17 | 3 |  |
| `rejected_reason` | 3 | 11 | 5 | 4 |  |
| `requested_by` | 17 | 60 | 25 | 4 |  |
| `rule_exception` | 0 | 2 | 0 | 0 | JARANG |
| `sales_order_customer` | 1 | 1 | 2 | 1 | JARANG |
| `sales_order_id` | 1 | 17 | 5 | 1 |  |
| `sales_order_number` | 1 | 5 | 9 | 1 |  |
| `source_entity_id` | 15 | 73 | 5 | 4 |  |
| `source_warehouse_id` | 17 | 41 | 17 | 4 |  |
| `status` | 17 | 6114 | 3268 | 8 |  |
| `transfer_kind` | 17 | 30 | 4 | 4 |  |
| `transfer_price` | 1 | 9 | 3 | 3 |  |
| `updated_at` | 17 | 1268 | 19 | 9 |  |

### putaway_orders (2 dok)
| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |
|---|---:|---:|---:|---:|---|
| `arrived_count` | 2 | 1 | 1 | 0 | JARANG |
| `btg_number` | 2 | 10 | 6 | 2 |  |
| `confirmed_at` | 2 | 22 | 1 | 2 |  |
| `confirmed_by` | 2 | 11 | 0 | 2 |  |
| `created_at` | 2 | 1255 | 118 | 2 |  |
| `created_by` | 2 | 566 | 57 | 2 |  |
| `dispatched_at` | 2 | 16 | 0 | 2 |  |
| `exception_count` | 2 | 2 | 2 | 0 |  |
| `from_warehouse_id` | 2 | 65 | 29 | 2 |  |
| `from_warehouse_name` | 2 | 5 | 2 | 2 |  |
| `id` | 2 | 9757 | 6977 | 2 |  |
| `item_count` | 2 | 16 | 10 | 0 |  |
| `items` | 2 | 2416 | 4841 | 3 |  |
| `mixed_units` | 2 | 2 | 1 | 0 | JARANG |
| `owner_entity_id` | 2 | 848 | 59 | 2 |  |
| `pa_number` | 2 | 39 | 5 | 2 |  |
| `qty_by_unit` | 2 | 18 | 8 | 0 |  |
| `status` | 2 | 6114 | 3268 | 3 |  |
| `to_warehouse_id` | 2 | 68 | 10 | 3 |  |
| `to_warehouse_name` | 2 | 16 | 5 | 3 |  |
| `total_qty` | 2 | 25 | 11 | 0 |  |
| `updated_at` | 2 | 1268 | 19 | 2 |  |

### rfid_tags (41 dok)
| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |
|---|---:|---:|---:|---:|---|
| `activated_at` | 14 | 3 | 0 | 2 | TULIS_TANPA_BACA (kandidat) |
| `encoded_at` | 41 | 3 | 0 | 1 | JARANG |
| `encoded_by` | 41 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `epc` | 41 | 317 | 55 | 2 |  |
| `id` | 41 | 9757 | 6977 | 1 |  |
| `last_seen_at` | 1 | 6 | 4 | 3 |  |
| `last_seen_device_id` | 1 | 3 | 0 | 3 | TULIS_TANPA_BACA (kandidat) |
| `last_seen_device_name` | 1 | 5 | 0 | 3 |  |
| `last_seen_location` | 0 | 5 | 2 | 3 |  |
| `last_seen_warehouse_id` | 1 | 5 | 0 | 3 |  |
| `lot` | 40 | 1073 | 701 | 1 |  |
| `owner_entity_id` | 41 | 848 | 59 | 2 |  |
| `product_id` | 41 | 2598 | 690 | 1 |  |
| `product_name` | 41 | 505 | 308 | 1 |  |
| `retire_reason` | 6 | 3 | 0 | 3 | TULIS_TANPA_BACA (kandidat) |
| `retired_at` | 6 | 4 | 0 | 4 | TULIS_TANPA_BACA (kandidat) |
| `roll_id` | 41 | 1100 | 282 | 1 |  |
| `roll_no` | 41 | 587 | 194 | 1 |  |
| `simulated` | 7 | 108 | 27 | 1 |  |
| `sku` | 41 | 1022 | 428 | 1 |  |
| `status` | 41 | 6114 | 3268 | 7 |  |
| `warehouse_id` | 41 | 1552 | 224 | 4 |  |

### rfid_verify_sessions (11 dok)
| field | dok berisi | sebutan BE | sebutan FE | panggilan tulis app | kelas |
|---|---:|---:|---:|---:|---|
| `completed_at` | 11 | 34 | 6 | 3 |  |
| `created_at` | 11 | 1255 | 118 | 3 |  |
| `created_by` | 11 | 566 | 57 | 3 |  |
| `expected` | 11 | 176 | 31 | 4 |  |
| `extra` | 4 | 255 | 128 | 4 |  |
| `id` | 11 | 9757 | 6977 | 3 |  |
| `job_number` | 8 | 20 | 8 | 1 |  |
| `kind` | 11 | 968 | 597 | 4 |  |
| `missing` | 0 | 207 | 109 | 4 |  |
| `not_committed_count` | 3 | 1 | 2 | 1 | JARANG |
| `order_id` | 3 | 1471 | 176 | 1 |  |
| `owner_entity_id` | 11 | 848 | 59 | 3 |  |
| `print_job_id` | 8 | 10 | 0 | 3 |  |
| `result` | 11 | 633 | 344 | 0 |  |
| `revision` | 8 | 31 | 69 | 1 |  |
| `scan_log` | 11 | 26 | 4 | 0 |  |
| `scan_sources` | 11 | 9 | 0 | 3 |  |
| `scanned_epcs` | 11 | 20 | 3 | 4 |  |
| `simulated_epcs` | 3 | 1 | 0 | 1 | TULIS_TANPA_BACA (kandidat) |
| `so_number` | 3 | 26 | 19 | 1 |  |
| `status` | 11 | 6114 | 3268 | 3 |  |
| `untagged` | 0 | 23 | 46 | 2 |  |
| `untagged_count` | 3 | 4 | 3 | 2 |  |
| `untagged_resolved` | 0 | 3 | 1 | 2 |  |
| `updated_at` | 11 | 1268 | 19 | 0 |  |
| `warehouse_id` | 11 | 1552 | 224 | 3 |  |


## B. Profil field

### `inventory_rolls` — 46700 dokumen diprofil, 389 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `acquired` | 100.0 | 100.0 | object:46700 |  |
| `acquired.date` | 100.0 | 100.0 | string:46700 | 2026-10-22T04:11:15.168643+0 · 2026-10-22T04:11:15.168675+0 · 2026-10-22T04:11:15.168694+0 |
| `acquired.ref_id` | 100.0 | 100.0 | string:46700 | seed · STOK_AWAL_KN · trn_16be328f7080 |
| `acquired.via` | 100.0 | 100.0 | string:46700 | initial · transfer · inbound |
| `acquired_history` | 0.0 | 0.0 | array:12 |  |
| `acquired_history[].date` | 0.0 | 0.0 | string:35 | 2026-10-22T04:16:02.912182+0 · 2026-10-22T04:16:03.104464+0 · 2026-10-22T04:16:03.104502+0 |
| `acquired_history[].inherited_at` | 0.0 | 0.0 | string:6 | 2026-10-22T18:50:50.512096+0 · 2026-10-22T18:50:50.514804+0 · 2026-10-22T18:50:50.517207+0 |
| `acquired_history[].inherited_from_roll_id` | 0.0 | 0.0 | string:6 | roll_46e00bbe9585 · roll_09e7412269c7 · roll_cut_rsv_7aa5b6f2d75f |
| `acquired_history[].owner_entity_name` | 0.0 | 0.0 | string:15 | Cipta Sandang · Sukacita |
| `acquired_history[].ref_id` | 0.0 | 0.0 | string:35 | STOK_AWAL_KN |
| `acquired_history[].replaced_at` | 0.0 | 0.0 | string:9 | 2026-10-22T07:17:56.806715+0 · 2026-10-22T07:17:56.849341+0 · 2026-10-22T07:17:56.785982+0 |
| `acquired_history[].replaced_by_transfer` | 0.0 | 0.0 | string:9 | CST/TRF-00002 |
| `acquired_history[].via` | 0.0 | 0.0 | string:35 | initial |
| `actual_task_qty` | 0.0 | 0.0 | number:10 | 91.44 · 100 · 200 |
| `base_unit_cost` | 100.0 | 100.0 | number:46700 | 0 · 31680 · 28800 |
| `batch` | 100.0 | 100.0 | string:46688 | BATCH-001 · BATCH-002 · SA-KNKNT0005 |
| `bin_code` | 0.0 | 0.0 | string:13 | A1-01 ·  · W05-L1-01 |
| `bin_id` | 100.0 | 79.7 | string:37221, null:9467 | bin_sim_hilang_01 · bin_sim_wh_jkt_w08_l4_05 · bin_sim_hilang_02 |
| `bin_sim` | 79.7 | 79.7 | string:37210 | SIMULASI_BIN_KN |
| `bucket_ref` | 0.2 | 0.2 | object:76, null:8 |  |
| `bucket_ref.created_at` | 0.2 | 0.2 | string:76 | 2026-11-03T21:49:51.586859+0 · 2026-10-22T04:17:32.009487+0 · 2026-10-22T04:17:32.152082+0 |
| `bucket_ref.created_by` | 0.2 | 0.2 | string:76 | Budi Santoso · Dewi Manager |
| `bucket_ref.id` | 0.2 | 0.2 | string:76 | mko_e446a412810a:1 · mko_4ae1fec91bc7:1 · mko_bbd5de93daad:1 |
| `bucket_ref.makloon_id` | 0.2 | 0.2 | string:76 | mak_1f50bdbd504f · mak_8386c3467c85 · mak_88b0d1fcd3b5 |
| `bucket_ref.makloon_name` | 0.2 | 0.2 | string:76 | PT Celup Warna Dayeuhkolot · CV Tenun Rancaekek · PT Rajut Cigondewah |
| `bucket_ref.mko_id` | 0.2 | 0.2 | string:76 | mko_e446a412810a · mko_4ae1fec91bc7 · mko_bbd5de93daad |
| `bucket_ref.mko_number` | 0.2 | 0.2 | string:76 | KSC/MKO-00081 · MKO-00001 · MKO-00002 |
| `bucket_ref.step` | 0.2 | 0.2 | number:76 | 1 |
| `bucket_ref.type` | 0.2 | 0.2 | string:76 | subcon |
| `committed_to` | 0.0 | 0.0 | null:13 |  |
| `condition` | 0.0 | 0.0 | null:1, string:12 | minor · ok |
| `consignor_ref` | 100.0 | 0.0 | null:46688 |  |
| `consumed_ref` | 0.1 | 0.1 | string:44 | mko_e446a412810a:1 · mko_bbd5de93daad:1 · mko_e7ef5aba2a55:1 |
| `cost_backfilled_at` | 0.0 | 0.0 | string:4 | 2026-10-23T18:09:22.358621+0 · 2026-10-23T18:09:22.375479+0 · 2026-10-23T18:09:22.392354+0 |
| `cost_basis` | 0.0 | 0.0 | object:9, string:4 | proxy_demo |
| `cost_basis.at` | 0.0 | 0.0 | string:9 | 2026-10-22T07:17:56.952768+0 · 2026-10-22T07:17:56.978688+0 · 2026-10-22T07:17:56.993525+0 |
| `cost_basis.interco_number` | 0.0 | 0.0 | string:9 | CST/IC-00001 |
| `cost_basis.interco_pair_id` | 0.0 | 0.0 | string:9 | icp_f41d6034cb48 |
| `cost_basis.previous_unit_cost` | 0.0 | 0.0 | number:9 | 12960 |
| `cost_basis.source` | 0.0 | 0.0 | string:9 | interco_purchase |
| `cost_missing` | 0.0 | 0.0 | boolean:4 | true |
| `created_at` | 100.0 | 100.0 | string:46700 | 2026-10-22T04:11:15.168653+0 · 2026-10-22T04:11:15.168678+0 · 2026-10-22T04:11:15.168696+0 |
| `created_by` | 100.0 | 100.0 | string:46688 | seed · Import Stok Awal · Demo Lengkap |
| `created_by_name` | 100.0 | 100.0 | string:46688 | System Seed · Import Stok Awal · Demo Lengkap |
| `cut` | 0.1 | 0.1 | object:40 |  |
| `cut.actual_length` | 0.1 | 0.1 | number:40 | 32.81 · 56.53 · 12.5 |
| `cut.at` | 0.1 | 0.1 | string:40 | 2026-10-22T17:19:30.341051+0 · 2026-10-22T17:37:49.025084+0 · 2026-10-23T00:34:08.933741+0 |
| `cut.by` | 0.1 | 0.1 | string:40 | Eko Warehouse |
| `cut.identity_verified` | 0.1 | 0.1 | boolean:40 | true · false |
| `cut.mode` | 0.1 | 0.1 | string:40 | manual |
| `cut.note` | 0.1 | 0.1 | string:40 | uji · uji F-10 · uji F-05 |
| `cut.reservation_id` | 0.1 | 0.1 | string:40 | rsv_0c63638931c0 · rsv_7aa5b6f2d75f · rsv_fdcac67897f2 |
| `cut.reserved_qty` | 0.1 | 0.1 | number:40 | 32.81 · 56.53 · 12.5 |
| `cut.verified_at` | 0.1 | 0.1 | string:39 | 2026-10-22T17:19:30.606173+0 · 2026-10-22T17:37:52.401382+0 · 2026-10-23T00:34:09.992075+0 |
| `cut.verified_by` | 0.1 | 0.1 | string:39 | Eko Warehouse |
| `cut.verified_ref` | 0.1 | 0.1 | string:39 | RL-20848-1 · RL-31985-1 · RL-20441-1 |
| `cut.verified_via` | 0.1 | 0.1 | string:39 | label_scan |
| `cut.waste` | 0.1 | 0.1 | number:40 | 0 |
| `declared_length` | 0.0 | 0.0 | null:10 |  |
| `declared_task_qty` | 0.0 | 0.0 | null:10 |  |
| `declared_weight_kg` | 0.0 | 0.0 | null:10 |  |
| `defects` | 100.0 | 0.0 | array:46700 |  |
| `defects[].code` | 0.0 | 0.0 | string:16 | CG · KO ·  |
| `defects[].count` | 0.0 | 0.0 | number:16 | 1 · 5 · 2 |
| `defects[].from_yard` | 0.0 | 0.0 | number:12 | 0 · 30 |
| `defects[].interval` | 0.0 | 0.0 | number:12 | 0 · 2 |
| `defects[].note` | 0.0 | 0.0 | string:16 |  · cacat |
| `defects[].point_value` | 0.0 | 0.0 | number:16 | 2 · 4 · 1 |
| `defects[].to_yard` | 0.0 | 0.0 | number:12 | 15 · 45 |
| `delivered_at` | 0.0 | 0.0 | string:13 | 2026-10-22T04:17:31.843034+0 · 2026-10-22T04:17:31.837019+0 · 2026-10-22T04:17:23.297319+0 |
| `dye_lot` | 100.0 | 100.0 | string:46700 | LOT-001 · LOT-002 · CST/LOT-2610-0001 |
| `earmarked_for` | 100.0 | 0.0 | null:46700 |  |
| `fabric_type` | 100.0 | 100.0 | string:46700 | woven · knit |
| `four_point_pending` | 0.1 | 0.1 | boolean:29 | true |
| `gate_exit` | 0.0 | 0.0 | object:1 |  |
| `gate_exit.at` | 0.0 | 0.0 | string:1 | 2026-11-03T21:49:51.920422+0 |
| `gate_exit.device_id` | 0.0 | 0.0 | string:1 | rdev_891088a797f4 |
| `gate_exit.movement_id` | 0.0 | 0.0 | string:1 | mko_e446a412810a:1 |
| `grade` | 100.0 | 100.0 | string:46700 | A · B · A1 |
| `grade_history` | 0.0 | 0.0 | array:15 |  |
| `grade_history[].changed_at` | 0.0 | 0.0 | string:19 | 2026-10-23T17:55:12.588496+0 · 2026-10-23T17:55:13.144204+0 · 2026-10-23T17:57:22.416718+0 |
| `grade_history[].changed_by` | 0.0 | 0.0 | string:19 | Budi Santoso · Mulyadi |
| `grade_history[].changed_by_id` | 0.0 | 0.0 | string:19 | user_admin_01 · user_03f0d6ed87f7 |
| `grade_history[].changed_by_role` | 0.0 | 0.0 | string:19 | admin · qc |
| `grade_history[].direction` | 0.0 | 0.0 | string:19 | tetap · turun |
| `grade_history[].grade_after` | 0.0 | 0.0 | string:19 | A · B · A1 |
| `grade_history[].grade_before` | 0.0 | 0.0 | string:19 | A · A1 |
| `grade_history[].inspection_note` | 0.0 | 0.0 | string:19 |  · noda KO · ada cacat parah pada roll |
| `grade_history[].points` | 0.0 | 0.0 | number:19 | 0 · 6 · 20 |
| `grade_history[].rank_after` | 0.0 | 0.0 | number:19 | 1 · 4 · 2 |
| `grade_history[].rank_before` | 0.0 | 0.0 | number:19 | 1 · 2 |
| `grade_history[].reason` | 0.0 | 0.0 | string:19 | Inspeksi 4-point: 0.0 poin · · Inspeksi 4-point: 6.0 poin · · Inspeksi 4-point: 20.0 poin  |
| `grade_history[].source` | 0.0 | 0.0 | string:19 | qc_inspection |
| `grade_history[].source_label` | 0.0 | 0.0 | string:19 | Inspeksi QC (4-point) |
| `grade_source` | 0.1 | 0.1 | string:52 | qc_inspection |
| `grade_updated_at` | 0.1 | 0.1 | string:52 | 2026-10-23T17:57:22.416718+0 · 2026-10-24T03:07:05.772658+0 · 2026-10-24T03:25:47.474580+0 |
| `grn_expected_seq` | 0.0 | 0.0 | null:10 |  |
| `grn_id` | 0.0 | 0.0 | string:10 | grn_cf59a3df6450 · grn_7f0061ddab7e · grn_0b673af1719b |
| `grn_line_no` | 0.0 | 0.0 | number:10 | 1 |
| `grn_task_id` | 0.1 | 0.1 | string:65 | wms_bef96c0e9725 · wms_fcd79c42d954 · wms_de7ca973f951 |
| `hold` | 0.0 | 0.0 | object:10 |  |
| `hold.at` | 0.0 | 0.0 | string:10 | 2026-10-23T17:57:22.509947+0 · 2026-10-24T03:07:05.888650+0 · 2026-10-24T03:25:47.605764+0 |
| `hold.by` | 0.0 | 0.0 | string:10 | Mulyadi · Budi Santoso |
| `hold.held` | 0.0 | 0.0 | boolean:10 | true · false |
| `hold.prev_status` | 0.0 | 0.0 | string:10 | available |
| `hold.reason` | 0.0 | 0.0 | string:10 | QC 4-point GAGAL — SPK KSC/I · QC 4-point GAGAL — SPK KSC/I · QC 4-point GAGAL — SPK KSC/I |
| `hold.release_note` | 0.0 | 0.0 | string:2 | Random check KSC/INS-00071 l · Random check KSC/INS-00017 l |
| `hold.released_at` | 0.0 | 0.0 | string:2 | 2026-10-23T17:56:34.268814+0 · 2026-10-22T18:53:55.265845+0 |
| `hold.released_by` | 0.0 | 0.0 | string:2 | Budi Santoso |
| `hold_history` | 0.0 | 0.0 | array:10 |  |
| `hold_history[].action` | 0.0 | 0.0 | string:12 | hold · release |
| `hold_history[].at` | 0.0 | 0.0 | string:12 | 2026-10-23T17:57:22.510001+0 · 2026-10-24T03:07:05.888721+0 · 2026-10-24T03:25:47.605842+0 |
| `hold_history[].by` | 0.0 | 0.0 | string:12 | Mulyadi · Budi Santoso |
| `hold_history[].by_id` | 0.0 | 0.0 | string:12 | user_03f0d6ed87f7 · user_admin_01 |
| `hold_history[].reason` | 0.0 | 0.0 | string:12 | QC 4-point GAGAL — SPK KSC/I · QC 4-point GAGAL — SPK KSC/I · QC 4-point GAGAL — SPK KSC/I |
| `hold_history[].status_from` | 0.0 | 0.0 | string:12 | available · blocked |
| `hold_history[].status_to` | 0.0 | 0.0 | string:12 | blocked · available |
| `id` | 100.0 | 100.0 | string:46700 | roll_4f30b238b48a · roll_0553e8c8bd04 · roll_66cbdbc7086f |
| `inspected_4point` | 0.0 | 0.0 | boolean:7 | true |
| `inspected_4point_at` | 0.0 | 0.0 | string:7 | 2026-10-24T03:07:05.774644+0 · 2026-10-24T03:25:47.477764+0 · 2026-10-24T03:26:31.244861+0 |
| `inspected_4point_by` | 0.0 | 0.0 | string:7 | Mulyadi |
| `inspected_4point_spk` | 0.0 | 0.0 | string:7 | KSC/INS-00092 · KSC/INS-00095 · KSC/INS-00098 |
| `inspection` | 0.2 | 0.2 | object:84, null:1 |  |
| `inspection.accepted_qty` | 0.0 | 0.0 | number:12 | 80.5 · 10 |
| `inspection.actual_qty` | 0.0 | 0.0 | number:2 | 60.5 · 20 |
| `inspection.baseline_sample_id` | 0.2 | 0.0 | string:72 |  · smp_7f562433dbec · smp_83f11b9d390d |
| `inspection.baseline_sample_number` | 0.2 | 0.0 | string:72 |  · KSC/SMP-00018 · KSC/SMP-00017 |
| `inspection.color_result` | 0.2 | 0.1 | string:72 |  · sesuai · beda_shade |
| `inspection.condition` | 0.0 | 0.0 | string:2 | ok · minor |
| `inspection.defects` | 0.0 | 0.0 | array:15 |  |
| `inspection.delta_e` | 0.2 | 0.0 | null:72 |  |
| `inspection.disposition` | 0.0 | 0.0 | string:2 |  |
| `inspection.dye_lot` | 0.0 | 0.0 | string:13 | LOT-001 · LOT-002 · KSC/LOT-2610-0008 |
| `inspection.form` | 0.0 | 0.0 | object:13 |  |
| `inspection.grade` | 0.1 | 0.1 | string:25 | B · A1 · A |
| `inspection.gsm_actual` | 0.0 | 0.0 | null:15 |  |
| `inspection.handfeel_result` | 0.2 | 0.1 | string:72 |  · sesuai |
| `inspection.handfeel_score` | 0.2 | 0.0 | null:72 |  |
| `inspection.hold` | 0.2 | 0.2 | object:72 |  |
| `inspection.inspected_at` | 0.0 | 0.0 | string:15 | 2026-10-23T17:57:22.415819+0 · 2026-10-24T03:07:05.771758+0 · 2026-10-24T03:25:47.473593+0 |
| `inspection.inspected_by` | 0.0 | 0.0 | string:15 | Mulyadi · Budi Santoso |
| `inspection.inspected_by_id` | 0.0 | 0.0 | string:13 | user_03f0d6ed87f7 · user_admin_01 |
| `inspection.inspection_doc_id` | 0.2 | 0.2 | string:72 | ins_1508866d4bc0 · ins_c719c3ff6245 · ins_18ffce4014fe |
| `inspection.inspection_doc_number` | 0.2 | 0.2 | string:72 | KSC/INS-00072 · KSC/INS-00092 · KSC/INS-00095 |
| `inspection.inspection_number` | 0.0 | 0.0 | string:2 | KSC/INS-00008 |
| `inspection.lot_id` | 0.0 | 0.0 | string:13 | lot_fd16f78f66e0 · lot_29965bc8aa33 · lot_230864ca1278 |
| `inspection.lot_number` | 0.0 | 0.0 | string:13 | KSC/LOT-2610-0001 · KSC/LOT-2610-0003 · KSC/LOT-2610-0007 |
| `inspection.lot_warnings` | 0.0 | 0.0 | array:13 |  |
| `inspection.md_quality_at` | 0.1 | 0.1 | string:59 | 2026-10-22T18:53:30.003551+0 · 2026-10-22T18:53:30.064262+0 · 2026-10-22T18:53:30.161125+0 |
| `inspection.md_quality_by` | 0.1 | 0.1 | string:59 | Lestari Wulandari · Budi Santoso |
| `inspection.md_quality_doc_id` | 0.1 | 0.1 | string:46 | ins_1fcbf0cfb78f · ins_428c99b88a1d · ins_414b8c9a1f86 |
| `inspection.md_quality_doc_number` | 0.1 | 0.1 | string:46 | KSC/INS-00052 · KSC/INS-00053 · KSC/INS-00054 |
| `inspection.note` | 0.0 | 0.0 | string:15 | noda KO ·  · ada cacat parah pada roll |
| `inspection.notes` | 0.0 | 0.0 | string:2 |  |
| `inspection.points` | 0.0 | 0.0 | number:15 | 6 · 0 · 20 |
| `inspection.raw_defects_input` | 0.0 | 0.0 | array:13 |  |
| `inspection.recommended_outcome` | 0.0 | 0.0 | string:2 | store_credit |
| `inspection.roll_actuals` | 0.0 | 0.0 | object:2 |  |
| `inspection.roll_no` | 0.0 | 0.0 | string:2 | RL-31983 · RL-31985-1 |
| `inspection.roll_results` | 0.0 | 0.0 | object:2 |  |
| `inspection.rule` | 0.0 | 0.0 | object:13 |  |
| `inspection.shade_ref` | 0.0 | 0.0 | string:13 |  |
| `inspection.source` | 0.0 | 0.0 | string:2 | spk |
| `inspection.supplier_lot` | 0.0 | 0.0 | string:13 |  |
| `inspection.thresholds` | 0.0 | 0.0 | object:15 |  |
| `inspection.width_actual` | 0.0 | 0.0 | number:6, null:9 | 147.32 |
| `is_remnant` | 100.0 | 100.0 | boolean:46688 | false · true |
| `is_sample_cut` | 0.0 | 0.0 | boolean:17 | true |
| `journey` | 0.3 | 0.3 | object:135, null:1 |  |
| `journey.print_job_id` | 0.0 | 0.0 | string:14 | rpj_01f2e6a14a87 · rpj_7b4fb21fc4b9 · rpj_a358acd053a3 |
| `journey.putaway_order_id` | 0.0 | 0.0 | string:2 | pa_5d903f9a571d · pa_a98e787b9fdc |
| `journey.routing` | 0.2 | 0.2 | string:85 | store |
| `journey.routing_by` | 0.0 | 0.0 | string:4 | Budi Santoso |
| `journey.stage` | 0.3 | 0.3 | string:135 | tag_verified · stored · received_transit |
| `journey.updated_at` | 0.3 | 0.3 | string:135 | 2026-10-23T17:48:16.135804+0 · 2026-10-23T17:48:17.041009+0 · 2026-10-23T17:48:19.943553+0 |
| `journey.verified_at` | 0.0 | 0.0 | string:14 | 2026-10-23T17:48:15.537890+0 · 2026-10-23T17:48:15.539122+0 · 2026-10-23T17:48:18.762238+0 |
| `journey.verified_tag_id` | 0.0 | 0.0 | string:14 | rtag_de19f89792f2 · rtag_34342c7e0282 · rtag_d34c9e208f6d |
| `journey.verify_session_id` | 0.0 | 0.0 | string:14 | rvs_1bc2553cc7cc · rvs_2f2195daff4e · rvs_297f9d711f89 |
| `label_variance` | 0.0 | 0.0 | null:10 |  |
| `landed_cost_refs` | 100.0 | 0.0 | array:46700 |  |
| `landed_cost_total` | 100.0 | 100.0 | number:46700 | 0 |
| `last_pa_landed` | 0.0 | 0.0 | string:2 | pa_5d903f9a571d · pa_a98e787b9fdc |
| `last_transfer` | 0.0 | 0.0 | object:1 |  |
| `last_transfer.code` | 0.0 | 0.0 | string:1 | CST/TRF-00001 |
| `last_transfer.date` | 0.0 | 0.0 | string:1 | 2026-10-22T04:17:19.524166+0 |
| `last_transfer.from_warehouse_id` | 0.0 | 0.0 | string:1 | wh_5ae35dcd8837 |
| `last_transfer.outcome` | 0.0 | 0.0 | string:1 | received |
| `last_transfer.received_by` | 0.0 | 0.0 | string:1 | Hana Safitri |
| `last_transfer.ref_id` | 0.0 | 0.0 | string:1 | trn_f4cfabf020b6 |
| `length` | 0.0 | 0.0 | null:1, number:12 | 60.5 · 20 · 10 |
| `length_initial` | 100.0 | 100.0 | number:46700 | 150 · 50 · 120 |
| `length_remaining` | 100.0 | 100.0 | number:46700 | 150 · 50 · 120 |
| `length_reservations` | 0.1 | 0.0 | array:53 |  |
| `length_reservations[].created_at` | 0.0 | 0.0 | string:34 | 2026-10-23T17:45:46.984778+0 · 2026-10-23T17:46:10.869021+0 · 2026-10-23T17:57:18.749375+0 |
| `length_reservations[].id` | 0.0 | 0.0 | string:34 | rsv_b262cbd2ad43 · rsv_bb5c2dab82de · rsv_77aee29ea995 |
| `length_reservations[].qty` | 0.0 | 0.0 | number:34 | 1 · 5 · 12.5 |
| `length_reservations[].ref` | 0.0 | 0.0 | object:34 |  |
| `length_reservations[].status` | 0.0 | 0.0 | string:34 | reserved · committed |
| `length_reserved` | 0.1 | 0.1 | number:53 | 6 · 0 · 5 |
| `line_code` | 100.0 | 99.9 | string:46700 |  · knit · printing |
| `location_type` | 100.0 | 100.0 | string:46688 | warehouse_bin |
| `lot` | 100.0 | 100.0 | string:46700 | LOT-001 · LOT-002 · CST/LOT-2610-0001 |
| `lot_id` | 100.0 | 100.0 | string:46700 | lot_fd16f78f66e0 · lot_90d1c1aa5c54 · lot_29965bc8aa33 |
| `md_quality_checked` | 0.1 | 0.1 | boolean:33 | true |
| `md_quality_checked_at` | 0.1 | 0.1 | string:33 | 2026-10-24T03:07:08.763379+0 · 2026-10-24T03:07:08.827427+0 · 2026-10-24T03:25:50.298735+0 |
| `md_quality_checked_by` | 0.1 | 0.1 | string:33 | Lestari Wulandari · Budi Santoso |
| `md_quality_spk` | 0.1 | 0.1 | string:33 | KSC/INS-00093 · KSC/INS-00096 · KSC/INS-00099 |
| `measure_confirmed` | 0.0 | 0.0 | boolean:10 | true |
| `opname_found_code` | 0.0 | 0.0 | string:1 | ASING-0ba9a7 |
| `origin_ref` | 0.0 | 0.0 | null:1, string:12 | sret_54a918a82410 · sr_TEST_SP_8d4e47_2161 · sr_TEST_SP_0fc9d4_6c10 |
| `origin_type` | 0.0 | 0.0 | null:1, string:12 | return |
| `owner_entity_id` | 100.0 | 100.0 | string:46700 | ent_ksc · ent_82b52ed6ee8b · ent_kanda |
| `ownership_type` | 100.0 | 100.0 | string:46688 | internal |
| `parent_roll_id` | 0.2 | 0.2 | string:97 | roll_ffd9b320b54e · roll_e7acf34b3745 · roll_0b87a00edbcc |
| `parent_roll_no` | 0.0 | 0.0 | string:17 | RL-00015 · RL-34857 · RL-34686 |
| `pending_cut_ops` | 0.0 | 0.0 | array:23 |  |
| `po_id` | 0.1 | 0.1 | string:65 | po_5bfabb9a129a · po_f0aa53200b59 · po_13e87908b394 |
| `po_number` | 0.1 | 0.1 | string:65 | CST/PO-00001 · KSC/PO-00002 · KSC/PO-00010 |
| `product_id` | 100.0 | 100.0 | string:46700 | prod_batik_mega · prod_tenun_ikat · prod_lurik_classic |
| `qc_grade` | 0.1 | 0.1 | string:40 | A |
| `qc_passed_at` | 0.1 | 0.1 | string:40 | 2026-10-22T04:17:19.069177+0 · 2026-10-22T06:36:05.106004+0 · 2026-10-22T18:53:30.259322+0 |
| `qc_rejected_at` | 0.0 | 0.0 | string:12 | 2026-10-22T18:53:31.415539+0 · 2026-10-22T18:53:32.045092+0 · 2026-10-23T17:45:37.320950+0 |
| `qc_status` | 0.0 | 0.0 | null:1, string:12 | pending_release |
| `qc_task_id` | 0.1 | 0.0 | null:52, string:17 | wms_8f8b017225c3 · wms_ae201a910791 · wms_7781be94019c |
| `qc_via_sampling` | 0.1 | 0.1 | object:49 |  |
| `qc_via_sampling.at` | 0.1 | 0.1 | string:49 | 2026-10-22T18:53:30.338639+0 · 2026-10-22T18:53:31.467455+0 · 2026-10-22T18:53:32.113278+0 |
| `qc_via_sampling.inspected_rolls` | 0.1 | 0.1 | number:49 | 0 |
| `qc_via_sampling.task_id` | 0.1 | 0.1 | string:49 | wms_de7ca973f951 · wms_ca463945b75b · wms_27a69c861fed |
| `qc_via_sampling.total_rolls` | 0.1 | 0.1 | number:49 | 3 · 2 · 1 |
| `random_check_id` | 0.0 | 0.0 | string:4 | ins_13326d6f0178 · ins_ffb4a0064497 |
| `received_date` | 0.1 | 0.1 | string:65 | 2026-10-22T04:17:18.014007+0 · 2026-10-22T06:21:53.391242+0 · 2026-10-22T06:21:59.754552+0 |
| `regraded_from` | 0.0 | 0.0 | string:1 | A |
| `reject_reason` | 0.0 | 0.0 | string:12 | SPK KSC/INS-00010: Diterima  · Kain berlubang di banyak tit · SPK KSC/INS-00053: Diterima  |
| `reserved_ref` | 100.0 | 0.3 | object:136, null:46564 |  |
| `reserved_ref.id` | 0.3 | 0.3 | string:136 | so_de0b7894677a · so_80615ba43389 · so_02bb630a3110 |
| `reserved_ref.type` | 0.3 | 0.3 | string:136 | sales_order · transfer |
| `return_history` | 0.0 | 0.0 | array:3 |  |
| `return_history[].at` | 0.0 | 0.0 | string:2 | 2026-10-22T18:50:50.427103+0 |
| `return_history[].customer_id` | 0.0 | 0.0 | string:2 | cust_toko_kain |
| `return_history[].customer_name` | 0.0 | 0.0 | string:2 | Toko Kain Sejahtera |
| `return_history[].grade_after` | 0.0 | 0.0 | string:2 | A · B |
| `return_history[].grade_before` | 0.0 | 0.0 | string:2 | A |
| `return_history[].order_id` | 0.0 | 0.0 | string:2 | so_1b9c7562fb8e |
| `return_history[].order_number` | 0.0 | 0.0 | string:2 | KSC/SO-00016 |
| `return_history[].qty_actual` | 0.0 | 0.0 | number:2 | 60.5 · 20 |
| `return_history[].qty_claimed` | 0.0 | 0.0 | number:2 | 61.03 · 20 |
| `return_history[].qty_shipped_bruto` | 0.0 | 0.0 | number:2 | 61.03 · 56.53 |
| `return_history[].return_id` | 0.0 | 0.0 | string:2 | sret_54a918a82410 |
| `return_history[].return_number` | 0.0 | 0.0 | string:2 | SRET-00005 |
| `return_history[].shipment_no` | 0.0 | 0.0 | string:2 | KSC/SJ-00009 |
| `return_history[].source_roll_id` | 0.0 | 0.0 | string:2 | roll_46e00bbe9585 · roll_cut_rsv_7aa5b6f2d75f |
| `return_history[].source_roll_no` | 0.0 | 0.0 | string:2 | RL-31983 · RL-31985-1 |
| `return_history[].unit` | 0.0 | 0.0 | string:2 | yard |
| `return_id` | 0.0 | 0.0 | string:12 | sret_54a918a82410 · sr_TEST_SP_8d4e47_2161 · sr_TEST_SP_0fc9d4_6c10 |
| `returned_from_customer_ids` | 0.0 | 0.0 | array:3 |  |
| `returned_from_status` | 0.0 | 0.0 | string:3 | available · quarantine |
| `returned_ref` | 0.0 | 0.0 | object:7 |  |
| `returned_ref.id` | 0.0 | 0.0 | string:7 | pret_4a3b109fc448 · pret_c9803552cbc0 · pret_55c15bff2517 |
| `returned_ref.type` | 0.0 | 0.0 | string:7 | purchase_return |
| `rfid_tag_id` | 100.0 | 0.1 | null:46652, string:38 | rtag_de19f89792f2 · rtag_34342c7e0282 · rtag_d34c9e208f6d |
| `roll_no` | 100.0 | 100.0 | string:46700 | RL-00001 · RL-00002 · RL-00003 |
| `root_roll_id` | 0.2 | 0.2 | string:97 | roll_ffd9b320b54e · roll_e7acf34b3745 · roll_0b87a00edbcc |
| `scan_source` | 0.0 | 0.0 | string:10 | count |
| `secondary_measures` | 100.0 | 0.1 | null:46619, object:65 |  |
| `secondary_measures.kg` | 0.1 | 0.1 | number:65 | 500 · 17.099 · 7.544 |
| `shipped_at` | 0.2 | 0.2 | string:94 | 2026-10-22T06:41:13.384634+0 · 2026-10-22T06:41:13.388429+0 · 2026-10-22T06:41:13.392081+0 |
| `sim_anomaly` | 0.0 | 0.0 | object:12 |  |
| `sim_anomaly.batch` | 0.0 | 0.0 | string:12 | SIMULASI_BIN_KN |
| `sim_anomaly.prev_bin_id` | 0.0 | 0.0 | null:12 |  |
| `sim_anomaly.type` | 0.0 | 0.0 | string:12 | bin_tidak_ada_di_master · lebih_kapasitas · satuan_campur |
| `source_roll_ids` | 0.0 | 0.0 | array:2 |  |
| `split_from_roll_id` | 0.0 | 0.0 | string:2 | roll_c92de067ac30 |
| `stage` | 100.0 | 100.0 | string:46700 | finished · yarn · grey |
| `status` | 100.0 | 100.0 | string:46700 | committed · blocked · in_transit_sales |
| `supplier_color` | 0.0 | 0.0 | string:8 |  · Navy Khusus 07 · Dark Navy |
| `supplier_dn_number` | 0.1 | 0.0 | string:65 |  · test · SJ-OD-8bbca |
| `supplier_id` | 0.2 | 0.2 | string:71 | sup_3a8f1bdfc994 · sup_030091f8255b · sup_a47057e2dfc2 |
| `supplier_invoice_no` | 0.1 | 0.0 | string:65 | INV-BSA-9A129A ·  |
| `supplier_item_name` | 0.0 | 0.0 | string:8 | Rayon motif kawung navy — SO · Katun twill warna khusus — S · Twill Cotton 40s Combed |
| `supplier_lot` | 99.9 | 0.0 | string:46668 |  · a · LOT-00015 |
| `supplier_name` | 0.2 | 0.2 | string:71 | PT Kain Jadi Nusantara · PT Benang Sejahtera Abadi · CV Grey Mandiri Majalaya |
| `supplier_return_ref` | 0.0 | 0.0 | object:1, null:1 |  |
| `supplier_return_ref.id` | 0.0 | 0.0 | string:1 | pret_c9803552cbc0 |
| `supplier_return_ref.type` | 0.0 | 0.0 | string:1 | purchase_return |
| `supplier_sku` | 0.0 | 0.0 | string:8 | 317401-DFC2 · E56E71-DFC2 · KJN-TW40-077 |
| `tracking_mode` | 100.0 | 100.0 | string:46688 | barcode · rfid |
| `transfer_prior_status` | 0.0 | 0.0 | string:10, null:1 | reserved |
| `transfer_ref` | 0.0 | 0.0 | object:10, null:1 |  |
| `transfer_ref.id` | 0.0 | 0.0 | string:10 | trn_ce9efaace0e8 |
| `transfer_ref.so_id` | 0.0 | 0.0 | string:10 | so_a892e48b62a2 |
| `transfer_ref.type` | 0.0 | 0.0 | string:10 | wh_transfer |
| `unit` | 100.0 | 100.0 | string:46700 | yard · kg · meter |
| `unit_cost` | 100.0 | 100.0 | null:16, number:46684 | 31680 · 28800 · 32400 |
| `updated_at` | 100.0 | 100.0 | string:46700 | 2026-10-22T07:03:53.679792+0 · 2026-10-22T07:03:53.684953+0 · 2026-10-22T07:03:53.674398+0 |
| `usage_history` | 0.0 | 0.0 | array:9 |  |
| `vendor_bill_id` | 0.1 | 0.0 | string:65 | vbill_c0ae08634248 · vbill_f24270cefc8a ·  |
| `warehouse_id` | 100.0 | 100.0 | string:46700 | wh_jakarta · wh_adc8726d019e · wh_fe25df27918e |
| `weight_kg` | 0.1 | 0.1 | number:65, null:4 | 500 · 17.099 · 7.544 |
| `weight_unit` | 0.1 | 0.1 | string:65 | kg |

### `inventory_balances` — 393 dokumen diprofil, 49 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `atp_qty` | 100.0 | 100.0 | number:393 | 10 · 0 · 80 |
| `available_qty` | 100.0 | 100.0 | number:393 | 10 · 0 · 80 |
| `blocked_qty` | 100.0 | 100.0 | number:393 | 50 · 0 · 55 |
| `committed_qty` | 100.0 | 100.0 | number:393 | 500 · 0 · 24.58 |
| `damaged_qty` | 100.0 | 100.0 | number:393 | 0 · 400 |
| `hold_qty` | 100.0 | 100.0 | number:393 | 0 · 50 |
| `id` | 100.0 | 100.0 | string:393 | bal_473fa9406369 · bal_0bb5af2a1734 · bal_8c610e18fa67 |
| `in_transit_inbound_qty` | 100.0 | 100.0 | number:393 | 0 |
| `in_transit_intercompany_qty` | 100.0 | 100.0 | number:393 | 0 |
| `in_transit_qty` | 100.0 | 100.0 | number:393 | 0 · 800 · 5 |
| `in_transit_sales_qty` | 100.0 | 100.0 | number:393 | 0 · 800 · 5 |
| `in_transit_transfer_qty` | 100.0 | 100.0 | number:393 | 0 · 250.65 |
| `incoming_qty` | 100.0 | 100.0 | number:393 | 0 · 1500 |
| `on_hand_qty` | 100.0 | 100.0 | number:393 | 562 · 0 · 80 |
| `on_hand_roll_count` | 100.0 | 100.0 | number:393 | 6 · 0 · 1 |
| `on_order_qty` | 100.0 | 100.0 | number:393 | 0 · 1500 |
| `owned_qty` | 100.0 | 100.0 | number:393 | 562 · 0 · 80 |
| `owner_entity_id` | 100.0 | 100.0 | string:393 | ent_ksc · ent_82b52ed6ee8b · ent_kanda |
| `packed_qty` | 100.0 | 100.0 | number:393 | 0 |
| `pending_demand_qty` | 100.0 | 100.0 | number:393 | 0 · 1050 |
| `picked_qty` | 100.0 | 100.0 | number:393 | 0 |
| `product_id` | 100.0 | 100.0 | string:393 | prod_batik_mega · prod_tenun_ikat · prod_songket_palembang |
| `projection_valid` | 100.0 | 100.0 | boolean:393 | true |
| `quarantine_qty` | 100.0 | 100.0 | number:393 | 0 · 59 · 80.5 |
| `rebuild_applied` | 100.0 | 100.0 | number:393 | 255 · 8 · 6 |
| `rebuild_ticket` | 100.0 | 100.0 | number:393 | 255 · 8 · 6 |
| `reserved_qty` | 100.0 | 100.0 | number:393 | 2 · 0 · 419.41 |
| `roll_count` | 100.0 | 100.0 | number:393 | 1 · 0 · 450 |
| `roll_counts` | 100.0 | 100.0 | object:393 |  |
| `roll_counts.available_qty` | 100.0 | 100.0 | number:393 | 1 · 0 · 450 |
| `roll_counts.blocked_qty` | 100.0 | 100.0 | number:393 | 1 · 0 · 3 |
| `roll_counts.committed_qty` | 100.0 | 100.0 | number:393 | 4 · 0 · 1 |
| `roll_counts.damaged_qty` | 100.0 | 100.0 | number:393 | 0 · 8 |
| `roll_counts.hold_qty` | 100.0 | 100.0 | number:393 | 0 · 1 |
| `roll_counts.in_transit_inbound_qty` | 100.0 | 100.0 | number:393 | 0 |
| `roll_counts.in_transit_intercompany_qty` | 100.0 | 100.0 | number:393 | 0 |
| `roll_counts.in_transit_sales_qty` | 100.0 | 100.0 | number:393 | 0 · 6 · 1 |
| `roll_counts.in_transit_transfer_qty` | 100.0 | 100.0 | number:393 | 0 · 10 |
| `roll_counts.packed_qty` | 100.0 | 100.0 | number:393 | 0 |
| `roll_counts.picked_qty` | 100.0 | 100.0 | number:393 | 0 |
| `roll_counts.quarantine_qty` | 100.0 | 100.0 | number:393 | 0 · 1 · 2 |
| `roll_counts.reserved_qty` | 100.0 | 100.0 | number:393 | 0 · 3 · 2 |
| `roll_counts.subcon_qty` | 100.0 | 100.0 | number:393 | 0 · 12 · 8 |
| `roll_counts.wip_qty` | 100.0 | 100.0 | number:393 | 0 |
| `subcon_qty` | 100.0 | 100.0 | number:393 | 0 · 300 · 200 |
| `unconvertible_roll_count` | 100.0 | 100.0 | number:393 | 0 |
| `updated_at` | 100.0 | 100.0 | string:393 | 2026-11-03T21:12:56.424423+0 · 2026-10-23T17:48:19.928671+0 · 2026-11-03T21:12:54.247158+0 |
| `warehouse_id` | 100.0 | 100.0 | string:393 | wh_jakarta · wh_fe25df27918e · wh_adc8726d019e |
| `wip_qty` | 100.0 | 100.0 | number:393 | 0 |

### `inventory_movements` — 50000 dokumen diprofil, 22 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `batch` | 93.0 | 93.0 | string:46510 | BTK-2024-001 · TNI-2024-001 · LRK-2024-001 |
| `by` | 0.0 | 0.0 | string:1 | Hana Safitri |
| `created_by` | 93.0 | 93.0 | string:46489 | Import Stok Awal · Demo Lengkap |
| `id` | 100.0 | 100.0 | string:50000 | mov_a91273789b7b · mov_1fe98b13c209 · mov_4576f88a0773 |
| `lot` | 100.0 | 100.0 | string:50000 | LOT-001 · LOT-002 · CST/LOT-2610-0001 |
| `lot_id` | 100.0 | 100.0 | string:49979 | lot_5d03a37692bd · lot_293d5e1eebad · lot_d8d1618ff470 |
| `movement_type` | 100.0 | 100.0 | string:50000 | initial_stock · inbound_receiving · qc_accept |
| `notes` | 93.0 | 93.0 | string:46489 | Stok awal migrasi (MOCK) · Stok awal demo (tahap bahan) · Stok retur demo grade B |
| `owner_entity_id` | 100.0 | 100.0 | string:50000 | ent_ksc · ent_82b52ed6ee8b · ent_kanda |
| `product_id` | 100.0 | 100.0 | string:50000 | prod_batik_mega · prod_tenun_ikat · prod_lurik_classic |
| `qty_rolls` | 100.0 | 100.0 | number:49979 | 1 |
| `quantity` | 100.0 | 100.0 | number:50000 | 350 · 200 · 150 |
| `receipt_outcome` | 0.0 | 0.0 | string:1 | received |
| `ref_id` | 0.0 | 0.0 | string:1 | wms_bef96c0e9725 |
| `ref_type` | 0.0 | 0.0 | string:1 | qc_inspection |
| `roll_id` | 100.0 | 100.0 | string:50000 | ROLL-001 · ROLL-002 · ROLL-003 |
| `sim_batch` | 6.8 | 6.8 | string:3406 | SIMULASI_BIN_KN |
| `source_document` | 100.0 | 100.0 | string:50000 | seed · STOK_AWAL_KN · STOK_AWAL_DEMO |
| `timestamp` | 100.0 | 100.0 | string:50000 | 2026-10-22T04:11:14.750861+0 · 2026-10-22T04:11:14.750877+0 · 2026-10-22T04:11:14.750882+0 |
| `unit` | 100.0 | 100.0 | string:50000 | yard · kg · meter |
| `warehouse_id` | 100.0 | 100.0 | string:50000 | wh_jakarta · wh_bandung · wh_surabaya |
| `weight_kg` | 0.0 | 0.0 | number:1 | 500 |

### `inventory_lots` — 462 dokumen diprofil, 60 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `active_roll_count` | 100.0 | 100.0 | number:462 | 5 · 1 · 4 |
| `child_lot_ids` | 100.0 | 0.9 | array:462 |  |
| `created_at` | 100.0 | 100.0 | string:462 | 2026-10-22T04:11:15.261897+0 · 2026-10-22T04:11:15.294972+0 · 2026-10-22T04:11:15.311021+0 |
| `created_by` | 100.0 | 100.0 | string:462 | seed · Import Stok Awal · Demo Lengkap |
| `created_by_name` | 100.0 | 100.0 | string:462 | seed · Import Stok Awal · Demo Lengkap |
| `dye_lot` | 100.0 | 11.3 | string:462 | LOT-001 · LOT-002 ·  |
| `entity_id` | 100.0 | 100.0 | string:462 | ent_ksc · ent_82b52ed6ee8b · ent_kanda |
| `fabric_type` | 100.0 | 100.0 | string:462 | woven · knit |
| `id` | 100.0 | 100.0 | string:462 | lot_fd16f78f66e0 · lot_90d1c1aa5c54 · lot_29965bc8aa33 |
| `legacy_lot_codes` | 100.0 | 97.8 | array:462 |  |
| `lot_number` | 100.0 | 100.0 | string:462 | KSC/LOT-2610-0001 · KSC/LOT-2610-0002 · KSC/LOT-2610-0003 |
| `lot_status` | 100.0 | 100.0 | string:462 | released · karantina |
| `note` | 100.0 | 0.0 | string:462 |  |
| `owner_entity_id` | 100.0 | 100.0 | string:462 | ent_ksc · ent_82b52ed6ee8b · ent_kanda |
| `parent_lot_ids` | 100.0 | 1.5 | array:462 |  |
| `process` | 100.0 | 100.0 | object:462 |  |
| `process.partner_id` | 100.0 | 0.0 | string:462 |  |
| `process.partner_name` | 100.0 | 0.0 | string:462 |  |
| `process.process_type` | 100.0 | 0.0 | string:462 |  |
| `product_id` | 100.0 | 100.0 | string:462 | prod_batik_mega · prod_tenun_ikat · prod_lurik_classic |
| `product_name` | 100.0 | 100.0 | string:462 | Batik Mega Mendung Premium · Tenun Ikat Garuda Premium · Lurik Klasik Solo |
| `qty_available` | 100.0 | 100.0 | number:462 | 0 · 80 · 9002.06 |
| `qty_initial` | 100.0 | 100.0 | number:462 | 550 · 150 · 120 |
| `qty_remaining` | 100.0 | 100.0 | number:462 | 550 · 150 · 120 |
| `roll_count` | 100.0 | 100.0 | number:462 | 5 · 1 · 4 |
| `shade_ref` | 100.0 | 0.0 | string:462 |  |
| `sku` | 100.0 | 100.0 | string:462 | BTK-MEGA-001 · TNI-GRGD-001 · LRK-CLSC-001 |
| `source` | 100.0 | 100.0 | string:462 | migration · receiving · makloon |
| `source_ref` | 100.0 | 100.0 | object:462 |  |
| `source_ref.code` | 0.2 | 0.2 | string:1 | ASING-0ba9a7 |
| `source_ref.id` | 99.8 | 99.8 | string:461 | roll_4f30b238b48a · roll_ef29cb4553f3 · roll_da2d8b960bf8 |
| `source_ref.number` | 99.8 | 99.8 | string:461 | LOT-001 · LOT-002 · Stok awal migrasi |
| `source_ref.session_id` | 0.2 | 0.2 | string:1 | ccs_TEST_W1_0ba9a7_11 |
| `source_ref.type` | 100.0 | 100.0 | string:462 | legacy_roll · initial · wms_task |
| `stage` | 100.0 | 100.0 | string:462 | finished · yarn · grey |
| `status_breakdown` | 100.0 | 92.6 | object:462 |  |
| `status_breakdown.available` | 84.8 | 84.8 | number:392 | 80 · 9002.06 · 8596.37 |
| `status_breakdown.blocked` | 1.3 | 1.3 | number:6 | 50 · 120 · 55 |
| `status_breakdown.committed` | 1.7 | 1.7 | number:8 | 500 · 150 · 24.58 |
| `status_breakdown.consumed` | 0.6 | 0.6 | number:3 | 0 |
| `status_breakdown.damaged` | 0.9 | 0.9 | number:4 | 100 |
| `status_breakdown.delivered` | 1.5 | 1.5 | number:7 | 49.23 · 12.5 · 357.52 |
| `status_breakdown.in_transit_sales` | 6.7 | 6.7 | number:31 | 500 · 300 · 5 |
| `status_breakdown.in_transit_transfer` | 0.2 | 0.2 | number:1 | 250.65 |
| `status_breakdown.quarantine` | 5.2 | 5.2 | number:24 | 80.5 · 100 · 50 |
| `status_breakdown.reserved` | 1.3 | 1.3 | number:6 | 51.33 · 2 · 3 |
| `status_breakdown.returned_supplier` | 1.1 | 1.1 | number:5 | 74.61 · 50 |
| `status_breakdown.subcon` | 0.6 | 0.6 | number:3 | 300 · 200 · 170.77 |
| `status_history` | 100.0 | 100.0 | array:462 |  |
| `status_history[].reason` | 100.0 | 100.0 | string:462 | Lot dibentuk |
| `status_history[].status` | 100.0 | 100.0 | string:462 | released · karantina |
| `status_history[].timestamp` | 100.0 | 100.0 | string:462 | 2026-10-22T04:11:15.261874+0 · 2026-10-22T04:11:15.294954+0 · 2026-10-22T04:11:15.311007+0 |
| `status_history[].user` | 100.0 | 100.0 | string:462 | seed · Import Stok Awal · Demo Lengkap |
| `supplier_dn_numbers` | 2.6 | 2.6 | array:12 |  |
| `supplier_id` | 100.0 | 7.4 | string:462 |  · sup_030091f8255b · sup_3a8f1bdfc994 |
| `supplier_lot` | 100.0 | 1.9 | string:462 |  · a · LOT-00015 |
| `supplier_name` | 100.0 | 7.4 | string:462 |  · PT Benang Sejahtera Abadi · PT Kain Jadi Nusantara |
| `unit` | 100.0 | 100.0 | string:462 | yard · kg · meter |
| `updated_at` | 100.0 | 100.0 | string:462 | 2026-11-08T19:48:23.710827+0 · 2026-11-08T19:48:24.644173+0 · 2026-11-08T19:48:23.913239+0 |
| `warehouse_id` | 100.0 | 100.0 | string:462 | wh_jakarta · wh_fe25df27918e · wh_40e831c5bb53 |

### `wms_tasks` — 252 dokumen diprofil, 190 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `allocation_id` | 48.8 | 47.6 | string:120, null:3 | alloc_db0da99aa21f · alloc_815a156490da · alloc_e99dd894febb |
| `assigned_to` | 0.8 | 0.8 | string:2 | user_68c468257b34 |
| `assigned_to_name` | 0.8 | 0.8 | string:2 | Hana Safitri |
| `batch` | 100.0 | 11.1 | string:252 | DM-9A129A · DM-C08C22 ·  |
| `bin_id` | 100.0 | 12.7 | string:252 |  · bin_sim_wh_jkt_w10_l4_02 · bin_sim_wh_jkt_w09_l1_03 |
| `cancel_reason` | 6.3 | 6.3 | string:16 | SO dibatalkan |
| `cancelled_by` | 6.3 | 6.3 | string:16 | Budi Santoso |
| `child_roll_no` | 6.7 | 6.7 | string:17 | RL-00015-1 · RL-33438-1 · RL-33624-1 |
| `conversion_variance` | 13.1 | 13.1 | object:33 |  |
| `conversion_variance.actual_kg` | 13.1 | 13.1 | number:33 | 500 · 22.632 · 15.088 |
| `conversion_variance.allow_override` | 13.1 | 13.1 | boolean:33 | true |
| `conversion_variance.block_pct` | 13.1 | 13.1 | number:33 | 5 |
| `conversion_variance.expected_kg` | 13.1 | 13.1 | number:33 | 500 · 22.63 · 15.09 |
| `conversion_variance.factor` | 13.1 | 13.1 | number:33 | 1 · 0.150876 · 0.174 |
| `conversion_variance.level` | 13.1 | 13.1 | string:33 | ok |
| `conversion_variance.message` | 13.1 | 0.0 | string:33 |  |
| `conversion_variance.variance_pct` | 13.1 | 13.1 | number:33 | 0 · 0.009 · -0.013 |
| `conversion_variance.warn_pct` | 13.1 | 13.1 | number:33 | 2 |
| `created_at` | 100.0 | 100.0 | string:252 | 2026-10-22T04:17:17.104830+0 · 2026-10-22T04:17:19.728964+0 · 2026-10-22T04:17:21.032027+0 |
| `created_by` | 100.0 | 100.0 | string:252 | Admin · Rina Kartika · Nadia Putri |
| `customer_name` | 7.9 | 7.9 | string:20 | Butik Bali Indah · Toko Kain Sejahtera |
| `cut_at` | 6.7 | 6.7 | string:17 | 2026-10-22T07:34:10.262540+0 · 2026-10-22T07:43:34.277234+0 · 2026-10-22T07:43:31.111960+0 |
| `cut_by` | 6.7 | 6.7 | string:17 | Budi Santoso · Eko Warehouse |
| `cutting_handoff` | 6.7 | 6.7 | object:17 |  |
| `cutting_handoff.from_warehouse_id` | 6.7 | 6.7 | string:17 | wh_jakarta |
| `cutting_handoff.received_at` | 6.7 | 6.7 | string:17 | 2026-10-22T07:44:09.045143+0 · 2026-10-22T07:44:10.578286+0 · 2026-10-22T07:44:14.474094+0 |
| `cutting_handoff.received_by` | 6.7 | 6.7 | string:17 | Budi Santoso · Yoga Admin Sample |
| `cutting_handoff.received_by_id` | 6.7 | 6.7 | string:17 | user_admin_01 · user_smpadmin_01 |
| `cutting_handoff.to_warehouse_id` | 6.7 | 6.7 | string:17 | wh_jakarta |
| `cutting_handoff.transferred` | 6.7 | 6.7 | boolean:17 | false |
| `declared_grn_ids` | 3.2 | 3.2 | array:8 |  |
| `declared_qty_total` | 3.2 | 3.2 | number:8 | 100 · 200 |
| `dye_lot` | 10.3 | 0.0 | string:26 |  |
| `entity_id` | 100.0 | 100.0 | string:252 | ent_82b52ed6ee8b · ent_ksc · ent_kanda |
| `escalation` | 52.0 | 0.8 | null:129, object:2 |  |
| `escalation.escalated_at` | 0.8 | 0.8 | string:2 | 2026-10-25T15:50:37.097349+0 · 2026-10-25T21:57:27.244113+0 |
| `escalation.escalated_by` | 0.8 | 0.8 | string:2 | Eko Warehouse |
| `escalation.reason` | 0.8 | 0.8 | string:2 | uji iter314 |
| `escalation.reopened_at` | 0.8 | 0.8 | string:2 | 2026-10-25T15:50:37.155632+0 · 2026-10-25T21:57:27.298035+0 |
| `escalation.reopened_by` | 0.8 | 0.8 | string:2 | Dewi Manager |
| `escalation.resolution_notes` | 0.8 | 0.8 | string:2 | iter314 sukses |
| `escalation.resolved_at` | 0.8 | 0.8 | string:2 | 2026-10-25T15:50:37.184553+0 · 2026-10-25T21:57:27.326067+0 |
| `escalation.resolved_by` | 0.8 | 0.8 | string:2 | Dewi Manager |
| `escalation.status` | 0.8 | 0.8 | string:2 | resolved |
| `expected_grade` | 50.4 | 48.4 | string:127 | A ·  |
| `expected_qty` | 51.2 | 51.2 | number:129 | 500 · 2000 · 1500 |
| `expected_rolls` | 51.2 | 0.8 | null:127, number:2 | 1 · 3 |
| `flow_type` | 100.0 | 100.0 | string:252 | inbound · outbound |
| `fulfillment_method` | 48.8 | 48.8 | string:123 | kirim |
| `gl_posting` | 13.1 | 13.1 | object:33 |  |
| `gl_posting.amount` | 13.1 | 13.1 | number:33 | 26000000 · 2100000 · 1400000 |
| `gl_posting.at` | 13.1 | 13.1 | string:33 | 2026-10-22T04:17:18.035770+0 · 2026-10-22T18:53:29.753004+0 · 2026-10-22T18:53:30.686566+0 |
| `gl_posting.entity_id` | 13.1 | 13.1 | string:33 | ent_82b52ed6ee8b · ent_ksc |
| `gl_posting.error` | 13.1 | 0.0 | string:33 |  |
| `gl_posting.je_id` | 13.1 | 13.1 | string:33 | je_9919f5ee9e99 · je_f74f632b4427 · je_2acf35bb9fc7 |
| `gl_posting.label` | 13.1 | 13.1 | string:33 | CST/PO-00001 · KSC/PO-00010 · KSC/PO-00011 |
| `gl_posting.status` | 13.1 | 13.1 | string:33 | posted |
| `grade` | 10.3 | 10.3 | string:26 | A |
| `grn_id` | 0.8 | 0.0 | string:2 |  |
| `grn_ids` | 3.2 | 3.2 | array:8 |  |
| `grn_number` | 0.8 | 0.0 | string:2 |  |
| `hold_until` | 48.8 | 0.0 | string:123 |  |
| `id` | 100.0 | 100.0 | string:252 | wms_bef96c0e9725 · wms_0ab7d8f5f162 · wms_7e9b4ea7a007 |
| `last_shipment_id` | 23.8 | 23.8 | string:60 | shp_7ffb0fe61d3f · shp_7044c9d09733 · shp_5faf8abf7225 |
| `line_code` | 0.8 | 0.8 | string:2 | printing · knit |
| `line_product_id` | 7.9 | 7.9 | string:20 | prod_ulos_batak · prod_7898868c4cfd · prod_b0b1698b1f3f |
| `lot` | 100.0 | 33.3 | string:252 | DM-LOT-9A129A · DM-LOT-C08C22 ·  |
| `lot_ids` | 13.9 | 13.9 | array:35 |  |
| `lot_numbers` | 13.1 | 13.1 | array:33 |  |
| `lot_warnings` | 13.1 | 9.9 | array:33 |  |
| `makloon_id` | 0.8 | 0.8 | string:2 | mak_8712ebef0a86 · mak_1f50bdbd504f |
| `mko_id` | 0.8 | 0.8 | string:2 | mko_e2da0b3d69fb · mko_e446a412810a |
| `mko_number` | 0.8 | 0.8 | string:2 | KSC/MKO-00050 · KSC/MKO-00081 |
| `needs_review` | 13.1 | 13.1 | boolean:33 | false |
| `off_suggestion_reason` | 6.7 | 0.0 | string:17 |  |
| `order_id` | 48.8 | 48.8 | string:123 | so_3ee0456e1a42 · so_9a758f00035e · so_1b25b6e63b83 |
| `order_number` | 48.8 | 48.8 | string:123 | KSC/SO-00001 · KSC/SO-00002 · KSC/SO-00003 |
| `order_type` | 7.9 | 7.9 | string:20 | sample |
| `over_receipt` | 13.5 | 13.5 | boolean:34 | false |
| `over_receipt_note` | 10.3 | 0.0 | string:26 |  |
| `owner_entity_id` | 0.8 | 0.8 | string:2 | ent_ksc |
| `parent_roll_id` | 6.7 | 6.7 | string:17 | roll_e78a8c70e3d9 · roll_6fe557a5be8c · roll_904426fcceab |
| `parent_roll_no` | 6.7 | 6.7 | string:17 | RL-00015 · RL-33438 · RL-33624 |
| `picked_qty` | 48.8 | 48.8 | number:123 | 353.79 · 357.52 · 484.56 |
| `po_id` | 51.2 | 50.4 | string:129 | po_5bfabb9a129a · po_59eb88c08c22 · po_4f65dcb9952a |
| `po_number` | 51.2 | 50.4 | string:129 | CST/PO-00001 · KSC/PO-00001 · KANDA/PO-00001 |
| `product_id` | 100.0 | 100.0 | string:252 | prod_cc00b3aed90e · prod_97ef39b63081 · prod_e867010c6127 |
| `product_name` | 100.0 | 100.0 | string:252 | Benang Katun 30s (untuk Tenu · Grey Woven Katun Poplin · LYFLEX ACTIVE NAVY A |
| `qc_accept_qty` | 8.7 | 8.7 | number:22 | 500 · 150 · 100 |
| `qc_at` | 8.7 | 8.7 | string:22 | 2026-10-22T04:17:19.105544+0 · 2026-10-22T18:53:30.338591+0 · 2026-10-22T18:53:31.467414+0 |
| `qc_by` | 8.7 | 8.7 | string:22 | Mulyadi · Budi Santoso |
| `qc_coverage` | 8.7 | 8.7 | object:22 |  |
| `qc_coverage.coverage_pct` | 8.7 | 8.7 | number:22 | 100 · 0 |
| `qc_coverage.decision_applies_to_uninspected` | 8.7 | 8.7 | boolean:22 | false · true |
| `qc_coverage.inspected_rolls` | 8.7 | 8.7 | number:22 | 1 · 0 |
| `qc_coverage.met` | 8.7 | 8.7 | boolean:22 | true |
| `qc_coverage.mode` | 8.7 | 8.7 | string:22 | all · none |
| `qc_coverage.planned_at` | 8.7 | 0.0 | null:22 |  |
| `qc_coverage.planned_by` | 8.7 | 0.0 | null:22 |  |
| `qc_coverage.required_rolls` | 8.7 | 8.7 | number:22 | 1 · 0 |
| `qc_coverage.sample_min` | 8.7 | 0.0 | null:22 |  |
| `qc_coverage.sample_pct` | 8.7 | 0.0 | null:22 |  |
| `qc_coverage.total_rolls` | 8.7 | 8.7 | number:22 | 1 · 3 · 2 |
| `qc_reason` | 8.7 | 8.7 | string:22 | Lolos inspeksi 4-point (demo · SPK KSC/INS-00009: Diterima  · SPK KSC/INS-00010: Diterima  |
| `qc_reject_disposition` | 8.7 | 3.2 | null:14, string:8 | return · damaged |
| `qc_reject_qty` | 8.7 | 8.7 | number:22 | 0 · 50 · 100 |
| `qc_status` | 13.9 | 13.9 | string:35 | passed · partial · rejected |
| `qty_rolls` | 51.2 | 13.9 | number:35, null:94 | 1 · 3 · 2 |
| `qty_rolls_scanned` | 3.2 | 3.2 | number:8 | 1 |
| `quantity` | 100.0 | 100.0 | number:252 | 500 · 0 · 353.79 |
| `quarantine_qty` | 13.9 | 13.9 | number:35 | 500 · 150 · 100 |
| `receipt_role` | 0.8 | 0.8 | string:2 | output |
| `receive_mode` | 3.2 | 3.2 | string:8 | scan_label |
| `receive_tolerance_percent` | 10.3 | 10.3 | number:26 | 2 |
| `receive_variance_percent` | 10.3 | 10.3 | number:26 | 0 · -40 |
| `receive_within_tolerance` | 13.5 | 13.5 | boolean:34 | true · false |
| `received_qty` | 51.2 | 51.2 | number:129 | 500 · 1200 · 0 |
| `refs` | 100.0 | 73.0 | array:252 |  |
| `refs[].at` | 73.0 | 73.0 | string:245 | 2026-10-22T04:17:17.109024+0 · 2026-10-22T04:17:19.737847+0 · 2026-10-22T04:17:21.038725+0 |
| `refs[].doc_id` | 73.0 | 73.0 | string:245 | po_5bfabb9a129a · po_59eb88c08c22 · po_4f65dcb9952a |
| `refs[].doc_number` | 73.0 | 73.0 | string:245 | CST/PO-00001 · KSC/PO-00001 · KANDA/PO-00001 |
| `refs[].doc_type` | 73.0 | 73.0 | string:245 | purchase_order · sales_order · shipment |
| `refs[].note` | 73.0 | 73.0 | string:245 | penerimaan Benang Katun 30s  · penerimaan Grey Woven Katun  · penerimaan LYFLEX ACTIVE NAV |
| `refs[].rel` | 73.0 | 73.0 | string:245 | parent · fulfilled_by |
| `roll_id` | 100.0 | 32.5 | string:252 | DM-9A129A-020 · DM-C08C22-024 ·  |
| `sample_billing` | 7.9 | 7.9 | string:20 | free · paid |
| `scan_log` | 100.0 | 39.3 | array:252 |  |
| `scan_log[].actor` | 39.3 | 39.3 | string:257 | Gilang Ramadhan · Eko Warehouse · Fajar Nugroho |
| `scan_log[].actual_qty` | 39.3 | 39.3 | number:240 | 25 · 50 · 353.79 |
| `scan_log[].batch` | 29.4 | 11.1 | string:154 | DM-9A129A · DM-C08C22 ·  |
| `scan_log[].bin_id` | 29.4 | 12.7 | string:144, null:10 |  · bin_sim_wh_jkt_w10_l4_02 · bin_sim_wh_jkt_w_over_01 |
| `scan_log[].epc` | 6.7 | 0.0 | string:17 |  |
| `scan_log[].format` | 3.2 | 3.2 | string:8 | count |
| `scan_log[].from` | 6.7 | 6.7 | string:17 | wh_jakarta |
| `scan_log[].id` | 39.3 | 39.3 | string:257 | scan_7041c9782559 · scan_962218c4a5aa · scan_17cf7eaa8b27 |
| `scan_log[].lot` | 32.5 | 29.0 | string:162 | DM-LOT-9A129A · DM-LOT-C08C22 ·  |
| `scan_log[].manual` | 3.2 | 3.2 | boolean:8 | true |
| `scan_log[].roll_id` | 39.3 | 35.7 | string:179 | DM-9A129A-001 · DM-9A129A-002 · DM-9A129A-003 |
| `scan_log[].roll_no` | 9.9 | 9.9 | string:25 | RL-00015 · RL-33438 · RL-33624 |
| `scan_log[].rolls` | 23.8 | 23.8 | array:61 |  |
| `scan_log[].scan_type` | 39.3 | 39.3 | string:257 | receive · pick · dispatch |
| `scan_log[].shipment_id` | 23.8 | 23.8 | string:61 | shp_7ffb0fe61d3f · shp_7044c9d09733 · shp_5faf8abf7225 |
| `scan_log[].timestamp` | 39.3 | 39.3 | string:257 | 2026-10-22T04:17:17.493227+0 · 2026-10-22T04:17:17.519986+0 · 2026-10-22T04:17:17.545765+0 |
| `scan_log[].to` | 6.7 | 6.7 | string:17 | wh_jakarta |
| `shipped_qty` | 48.8 | 48.8 | number:123 | 353.79 · 357.52 · 484.56 |
| `sku` | 100.0 | 100.0 | string:252 | DMO-YRN-WVN-30S · DMO-GRY-WVN-001 · KNKNT0052-L-NVYX-XA-XX-XX |
| `source_type` | 100.0 | 100.0 | string:252 | purchase_order · sales_order · makloon_order |
| `special_order_id` | 0.8 | 0.0 | string:2 |  |
| `stages` | 100.0 | 100.0 | array:252 |  |
| `status` | 100.0 | 100.0 | string:252 | completed · cancelled · waiting_goods |
| `step_seq` | 0.8 | 0.8 | number:2 | 1 |
| `suggested_roll_id` | 7.9 | 7.1 | string:18, null:2 | roll_e78a8c70e3d9 · roll_6fe557a5be8c · roll_904426fcceab |
| `suggested_roll_no` | 7.9 | 7.1 | string:18, null:2 | RL-00015 · RL-33438 · RL-33624 |
| `supplier_conv_factor` | 50.4 | 50.4 | number:127 | 0 · 1 · 1.094 |
| `supplier_dn_missing` | 13.1 | 13.1 | boolean:33 | true · false |
| `supplier_dn_number` | 4.0 | 3.6 | string:10 | SJ-OD-8bbca · SJ-OD-93447 · SJ-DN-7d0d2 |
| `supplier_dn_numbers` | 3.2 | 3.2 | array:8 |  |
| `supplier_item_id` | 50.4 | 8.3 | string:127 |  · sit_5c87b6c21aea · sit_0f3b6d568395 |
| `supplier_item_name` | 50.4 | 8.3 | string:127 |  · Rayon motif kawung navy — SO · Katun twill warna khusus — S |
| `supplier_lot` | 13.1 | 3.2 | string:33 |  · LOT-00015 · LOT-00016 |
| `supplier_name` | 51.2 | 51.2 | string:129 | PT Benang Sejahtera Abadi · CV Grey Mandiri Majalaya · PT Kain Jadi Nusantara |
| `supplier_sku` | 50.4 | 8.3 | string:127 |  · 317401-DFC2 · E56E71-DFC2 |
| `supplier_uom` | 50.4 | 3.2 | string:127 |  · meter |
| `takeover_log` | 0.8 | 0.8 | array:2 |  |
| `takeover_log[].at` | 0.8 | 0.8 | string:2 | 2026-10-23T17:56:23.567848+0 · 2026-10-24T04:15:25.299330+0 |
| `takeover_log[].by` | 0.8 | 0.8 | string:2 | Hana Safitri |
| `takeover_log[].by_id` | 0.8 | 0.8 | string:2 | user_68c468257b34 |
| `takeover_log[].from` | 0.8 | 0.0 | string:2 |  |
| `takeover_log[].reason` | 0.8 | 0.8 | string:2 | p01 regression check |
| `takeover_log[].warehouse_id` | 0.8 | 0.8 | string:2 | wh_adc8726d019e · wh_jakarta |
| `task_subtype` | 8.7 | 8.7 | string:22 | sample_cut · makloon_receipt |
| `unit` | 100.0 | 100.0 | string:252 | kg · yard · meter |
| `unit_factor` | 50.4 | 0.0 | null:127 |  |
| `unit_factor_to` | 50.4 | 0.0 | string:127 |  |
| `uom_trail` | 13.1 | 13.1 | object:33 |  |
| `uom_trail.base_qty` | 13.1 | 13.1 | number:33 | 500 · 150 · 100 |
| `uom_trail.base_uom` | 13.1 | 13.1 | string:33 | kg · yard · meter |
| `uom_trail.context` | 13.1 | 13.1 | string:33 | goods_receipt |
| `uom_trail.converted_at` | 13.1 | 13.1 | string:33 | 2026-10-22T04:17:17.990131+0 · 2026-10-22T18:53:29.684636+0 · 2026-10-22T18:53:30.627044+0 |
| `uom_trail.doc_qty` | 13.1 | 13.1 | number:33 | 500 · 150 · 100 |
| `uom_trail.doc_uom` | 13.1 | 13.1 | string:33 | kg · yard · meter |
| `uom_trail.factor` | 13.1 | 13.1 | number:33 | 1 · 1.0936133 |
| `uom_trail.formula` | 13.1 | 0.0 | string:33 |  |
| `uom_trail.path` | 13.1 | 13.1 | array:33 |  |
| `uom_trail.rule_id` | 13.1 | 0.0 | string:33 |  |
| `uom_trail.source` | 13.1 | 13.1 | string:33 | same_unit · fixed_uom |
| `updated_at` | 100.0 | 100.0 | string:252 | 2026-10-22T04:17:19.105552+0 · 2026-10-25T21:57:26.932652+0 · 2026-10-22T04:17:21.039527+0 |
| `warehouse_city` | 100.0 | 100.0 | string:252 | Bandung · Jakarta · Kota Bandung |
| `warehouse_id` | 100.0 | 100.0 | string:252 | wh_5ae35dcd8837 · wh_jakarta · wh_40e831c5bb53 |
| `warehouse_name` | 100.0 | 100.0 | string:252 | Rancamalang · Gudang Transit · Jakarta · Gudang Sukacita · Soreang · Gudang Kanda |

### `warehouse_transfers` — 17 dokumen diprofil, 73 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `approved_at` | 100.0 | 17.6 | string:3, null:14 | 2026-10-22T04:17:19.347862+0 · 2026-10-22T04:18:15.427815+0 · 2026-10-22T07:17:57.959972+0 |
| `approved_by` | 100.0 | 17.6 | string:3, null:14 | Manager |
| `code` | 100.0 | 100.0 | string:17 | CST/TRF-00001 · KANDA/TRF-00001 · KSC/TRF-00001 |
| `completed_at` | 5.9 | 5.9 | string:1 | 2026-10-22T04:17:19.598295+0 |
| `completion_basis` | 5.9 | 5.9 | string:1 | actual_receipt |
| `created_at` | 100.0 | 100.0 | string:17 | 2026-10-22T04:17:19.316634+0 · 2026-10-22T04:18:15.396573+0 · 2026-10-23T17:55:53.189110+0 |
| `dest_entity_id` | 88.2 | 88.2 | string:15 | ent_kanda · ent_ksc |
| `dest_warehouse_id` | 100.0 | 100.0 | string:17 | wh_adc8726d019e · wh_5930cde7a951 · wh_jakarta |
| `entity_id` | 100.0 | 100.0 | string:17 | ent_82b52ed6ee8b · ent_kanda · ent_ksc |
| `id` | 100.0 | 100.0 | string:17 | trn_f4cfabf020b6 · trn_ce9efaace0e8 · trn_d08097449f7d |
| `interco_id` | 88.2 | 5.9 | null:14, string:1 | ict_184a77788dc0 |
| `interco_number` | 88.2 | 5.9 | string:15 |  · CST/IC-00001 |
| `interco_pair_id` | 88.2 | 5.9 | null:14, string:1 | icp_f41d6034cb48 |
| `items` | 100.0 | 100.0 | array:17 |  |
| `items[].batch` | 11.8 | 0.0 | string:2 |  |
| `items[].interco_unit_price` | 5.9 | 5.9 | number:1 | 12600 |
| `items[].line_code` | 100.0 | 100.0 | string:17 | woven · knit · printing |
| `items[].lot` | 11.8 | 0.0 | string:2 |  |
| `items[].lots` | 100.0 | 100.0 | array:17 |  |
| `items[].owner_entity_id` | 11.8 | 11.8 | string:2 | ent_82b52ed6ee8b · ent_kanda |
| `items[].product_id` | 100.0 | 100.0 | string:17 | prod_cc00b3aed90e · prod_e867010c6127 · prod_60f19f07ee06 |
| `items[].product_name` | 100.0 | 100.0 | string:17 | Benang Katun 30s (untuk Tenu · LYFLEX ACTIVE NAVY A · BABY CRUSH 1922 BABY BLUE A |
| `items[].qty` | 100.0 | 100.0 | number:17 | 500 · 250.65 · 1 |
| `items[].qty_rolls` | 94.1 | 94.1 | number:16 | 1 · 10 |
| `items[].roll_id` | 11.8 | 0.0 | string:2 |  |
| `items[].roll_ids` | 11.8 | 11.8 | array:2 |  |
| `items[].rolls` | 100.0 | 100.0 | array:17 |  |
| `items[].sku` | 100.0 | 100.0 | string:17 | DMO-YRN-WVN-30S · KNKNT0052-L-NVYX-XA-XX-XX · KNPRT0003-X-BBXX-XA-XX-XX |
| `items[].unit` | 100.0 | 100.0 | string:17 | kg · meter · yard |
| `items[].unit_cost_snapshot` | 5.9 | 5.9 | number:1 | 12960 |
| `je_intercompany` | 5.9 | 5.9 | object:1 |  |
| `je_intercompany.interco_pair_id` | 5.9 | 5.9 | string:1 | icp_f41d6034cb48 |
| `je_intercompany.interco_status` | 5.9 | 5.9 | string:1 | received |
| `je_intercompany.posted` | 5.9 | 5.9 | boolean:1 | false |
| `je_intercompany.revalued_rolls` | 5.9 | 5.9 | number:1 | 9 |
| `je_intercompany.skipped_reason` | 5.9 | 5.9 | string:1 | Jurnal sudah diposting oleh  |
| `line_codes` | 100.0 | 100.0 | array:17 |  |
| `linked_order_id` | 88.2 | 0.0 | null:15 |  |
| `notes` | 100.0 | 100.0 | string:17 | Putaway benang dari transit  · [CONTOH P03] Pemenuhan KANDA · M-3 test IC transfer |
| `ownership_moved` | 5.9 | 5.9 | object:1 |  |
| `ownership_moved.moved_qty` | 5.9 | 5.9 | number:1 | 500 |
| `ownership_moved.rolls` | 5.9 | 5.9 | number:1 | 9 |
| `receipt_events` | 5.9 | 5.9 | array:1 |  |
| `receipt_events[].at` | 5.9 | 5.9 | string:1 | 2026-10-22T04:17:19.562943+0 |
| `receipt_events[].bin_id` | 5.9 | 0.0 | string:1 |  |
| `receipt_events[].by` | 5.9 | 5.9 | string:1 | Hana Safitri |
| `receipt_events[].id` | 5.9 | 5.9 | string:1 | trc_f6b82e2b477e |
| `receipt_events[].note` | 5.9 | 5.9 | string:1 | Semua roll tiba (demo) |
| `receipt_events[].results` | 5.9 | 5.9 | array:1 |  |
| `refs` | 5.9 | 0.0 | array:1 |  |
| `rejected_at` | 100.0 | 17.6 | null:14, string:3 | 2026-10-23T17:55:53.579492+0 · 2026-10-25T15:51:31.170651+0 · 2026-10-25T21:58:23.863278+0 |
| `rejected_by` | 100.0 | 17.6 | null:14, string:3 | Manager |
| `rejected_reason` | 100.0 | 17.6 | null:14, string:3 | test |
| `requested_by` | 100.0 | 100.0 | string:17 | Warehouse User · Budi Santoso |
| `rule_exception` | 5.9 | 0.0 | null:1 |  |
| `sales_order_customer` | 5.9 | 5.9 | string:1 | Toko Tekstil Pasar Baru |
| `sales_order_id` | 5.9 | 5.9 | string:1 | so_a892e48b62a2 |
| `sales_order_number` | 5.9 | 5.9 | string:1 | KANDA/SO-00003 |
| `source_entity_id` | 88.2 | 88.2 | string:15 | ent_ksc · ent_82b52ed6ee8b |
| `source_warehouse_id` | 100.0 | 100.0 | string:17 | wh_5ae35dcd8837 · wh_40e831c5bb53 · wh_jakarta |
| `status` | 100.0 | 100.0 | string:17 | completed · dispatched · waiting_approval |
| `transfer_kind` | 100.0 | 100.0 | string:17 | intra_entity · inter_entity |
| `transfer_price` | 88.2 | 5.9 | null:14, number:1 | 6300000 |
| `updated_at` | 100.0 | 100.0 | string:17 | 2026-10-22T04:17:19.598278+0 · 2026-10-22T04:18:15.544293+0 · 2026-10-23T17:55:53.189124+0 |

### `putaway_orders` — 2 dokumen diprofil, 35 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `arrived_count` | 100.0 | 100.0 | number:2 | 1 |
| `btg_number` | 100.0 | 100.0 | string:2 | BTG00001 · BTG00002 |
| `confirmed_at` | 100.0 | 100.0 | string:2 | 2026-10-23T17:48:17.057059+0 · 2026-10-23T17:48:19.959699+0 |
| `confirmed_by` | 100.0 | 100.0 | string:2 | Budi Santoso |
| `created_at` | 100.0 | 100.0 | string:2 | 2026-10-23T17:48:16.715846+0 · 2026-10-23T17:48:19.624659+0 |
| `created_by` | 100.0 | 100.0 | string:2 | Budi Santoso |
| `dispatched_at` | 100.0 | 100.0 | string:2 | 2026-10-23T17:48:16.843477+0 · 2026-10-23T17:48:19.768766+0 |
| `exception_count` | 100.0 | 100.0 | number:2 | 0 |
| `from_warehouse_id` | 100.0 | 100.0 | string:2 | wh_jakarta |
| `from_warehouse_name` | 100.0 | 100.0 | string:2 | Jakarta · Gudang Sukacita |
| `id` | 100.0 | 100.0 | string:2 | pa_5d903f9a571d · pa_a98e787b9fdc |
| `item_count` | 100.0 | 100.0 | number:2 | 1 |
| `items` | 100.0 | 100.0 | array:2 |  |
| `items[].category` | 100.0 | 100.0 | string:2 | Tenun |
| `items[].epc` | 100.0 | 100.0 | string:2 | E2F6FF878012AF4A52ACDF70 · E2CE437A4452914BA1947471 |
| `items[].grade` | 100.0 | 100.0 | string:2 | A |
| `items[].lot` | 100.0 | 100.0 | string:2 | LOT-001 · LOT-002 |
| `items[].product_id` | 100.0 | 100.0 | string:2 | prod_tenun_ikat |
| `items[].product_name` | 100.0 | 100.0 | string:2 | Tenun Ikat Garuda Premium |
| `items[].qty` | 100.0 | 100.0 | number:2 | 150 · 120 |
| `items[].roll_id` | 100.0 | 100.0 | string:2 | roll_ef29cb4553f3 · roll_da2d8b960bf8 |
| `items[].roll_no` | 100.0 | 100.0 | string:2 | RL-00006 · RL-00007 |
| `items[].sku` | 100.0 | 100.0 | string:2 | TNI-GRGD-001 |
| `items[].status` | 100.0 | 100.0 | string:2 | arrived |
| `items[].unit` | 100.0 | 100.0 | string:2 | yard |
| `mixed_units` | 100.0 | 100.0 | boolean:2 | false |
| `owner_entity_id` | 100.0 | 100.0 | string:2 | ent_ksc |
| `pa_number` | 100.0 | 100.0 | string:2 | PA00001 · PA00002 |
| `qty_by_unit` | 100.0 | 100.0 | object:2 |  |
| `qty_by_unit.yard` | 100.0 | 100.0 | number:2 | 150 · 120 |
| `status` | 100.0 | 100.0 | string:2 | completed |
| `to_warehouse_id` | 100.0 | 100.0 | string:2 | wh_adc8726d019e |
| `to_warehouse_name` | 100.0 | 100.0 | string:2 | Rancamalang · Gudang Woven |
| `total_qty` | 100.0 | 100.0 | number:2 | 150 · 120 |
| `updated_at` | 100.0 | 100.0 | string:2 | 2026-10-23T17:48:17.057059+0 · 2026-10-23T17:48:19.959699+0 |

### `goods_receipts` — 15 dokumen diprofil, 123 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `active_key` | 53.3 | 53.3 | string:8 | ent_ksc/sup_a47057e2dfc2/SJO · ent_ksc/sup_a47057e2dfc2/SJO · ent_ksc/sup_3a8f1bdfc994/SJD |
| `cancel_reason` | 100.0 | 40.0 | string:15 |  · uji trial 22 okt B3 |
| `closed_at` | 100.0 | 53.3 | string:15 |  · 2026-10-23T02:08:01.462957+0 · 2026-10-23T02:08:10.921078+0 |
| `closed_by` | 100.0 | 53.3 | string:15 |  · Hendra Kepala Gudang |
| `closing_started_at` | 53.3 | 53.3 | string:8 | 2026-10-23T02:08:01.137717+0 · 2026-10-23T02:08:10.631956+0 · 2026-10-23T17:57:27.567229+0 |
| `count_finished_at` | 53.3 | 53.3 | string:8 | 2026-10-23T02:08:01.107024+0 · 2026-10-23T02:08:10.603487+0 · 2026-10-23T17:57:27.535375+0 |
| `count_started_at` | 53.3 | 53.3 | string:8 | 2026-10-23T02:08:00.912330+0 · 2026-10-23T02:08:10.439459+0 · 2026-10-23T17:57:27.334305+0 |
| `count_started_by` | 53.3 | 53.3 | string:8 | Hendra Kepala Gudang |
| `counted_by` | 100.0 | 53.3 | array:15 |  |
| `created_at` | 100.0 | 100.0 | string:15 | 2026-10-23T02:07:39.871612+0 · 2026-10-23T02:08:00.803099+0 · 2026-10-23T02:08:10.322875+0 |
| `created_by` | 100.0 | 100.0 | string:15 | Hendra Kepala Gudang |
| `discrepancies` | 100.0 | 0.0 | array:15 |  |
| `dn` | 100.0 | 100.0 | object:15 |  |
| `dn.annotations` | 100.0 | 0.0 | array:15 |  |
| `dn.date` | 100.0 | 0.0 | string:15 |  |
| `dn.date_text` | 100.0 | 0.0 | string:15 |  |
| `dn.edited_fields` | 100.0 | 60.0 | array:15 |  |
| `dn.number` | 100.0 | 60.0 | string:15 | SJ-OD-3952a · SJ-OD-8bbca · SJ-OD-93447 |
| `dn.number_norm` | 100.0 | 60.0 | string:15 | SJOD3952A · SJOD8BBCA · SJOD93447 |
| `dn.other_refs` | 100.0 | 0.0 | array:15 |  |
| `dn.po_refs` | 100.0 | 100.0 | array:15 |  |
| `dn.recipient_name` | 100.0 | 0.0 | string:15 |  |
| `dn.source` | 100.0 | 100.0 | string:15 | manual |
| `dn.supplier_name_printed` | 100.0 | 0.0 | string:15 |  |
| `dn.vehicle_plate` | 100.0 | 0.0 | string:15 |  |
| `dn.verified` | 60.0 | 60.0 | boolean:9 | true |
| `dn.verified_at` | 60.0 | 60.0 | string:9 | 2026-10-23T02:07:40.017622+0 · 2026-10-23T02:08:00.853810+0 · 2026-10-23T02:08:10.372114+0 |
| `dn.verified_by` | 60.0 | 60.0 | string:9 | Hendra Kepala Gudang |
| `entity_id` | 100.0 | 100.0 | string:15 | ent_ksc |
| `extraction` | 100.0 | 100.0 | object:15 |  |
| `extraction.error_code` | 100.0 | 0.0 | string:15 |  |
| `extraction.read_failed` | 100.0 | 100.0 | boolean:15 | false |
| `extraction.runs` | 100.0 | 0.0 | array:15 |  |
| `extraction.text_layer_used` | 100.0 | 100.0 | boolean:15 | false |
| `files` | 100.0 | 0.0 | array:15 |  |
| `id` | 100.0 | 100.0 | string:15 | grn_cd25b56ef219 · grn_7f0061ddab7e · grn_0b673af1719b |
| `lines` | 100.0 | 60.0 | array:15 |  |
| `lines[].checks` | 60.0 | 60.0 | object:9 |  |
| `lines[].converted` | 60.0 | 60.0 | object:9 |  |
| `lines[].counted` | 60.0 | 60.0 | object:9 |  |
| `lines[].decision` | 60.0 | 60.0 | string:9 | accept |
| `lines[].declared` | 60.0 | 60.0 | object:9 |  |
| `lines[].is_non_stock` | 60.0 | 60.0 | boolean:9 | false |
| `lines[].line_no` | 60.0 | 60.0 | number:9 | 1 |
| `lines[].match` | 60.0 | 60.0 | object:9 |  |
| `lines[].page` | 60.0 | 60.0 | number:9 | 1 |
| `lines[].posted` | 60.0 | 60.0 | object:9 |  |
| `lines[].read` | 60.0 | 60.0 | object:9 |  |
| `lines[].recon` | 60.0 | 53.3 | null:1, object:8 |  |
| `lines[].role` | 60.0 | 60.0 | string:9 | output |
| `lines[].target` | 60.0 | 60.0 | object:9 |  |
| `lines[].verified` | 60.0 | 60.0 | boolean:9 | true |
| `lines[].verified_by` | 60.0 | 60.0 | string:9 | Hendra Kepala Gudang |
| `number` | 100.0 | 100.0 | string:15 | KSC/GRN-00002 · KSC/GRN-00003 · KSC/GRN-00004 |
| `partner_id` | 100.0 | 100.0 | string:15 | sup_a47057e2dfc2 · sup_3a8f1bdfc994 |
| `partner_name` | 100.0 | 100.0 | string:15 | CV Grey Mandiri Majalaya · PT Kain Jadi Nusantara |
| `partner_type` | 100.0 | 100.0 | string:15 | supplier |
| `refs` | 100.0 | 100.0 | array:15 |  |
| `refs[].at` | 100.0 | 100.0 | string:15 | 2026-10-23T02:07:39.931876+0 · 2026-10-23T02:08:00.808025+0 · 2026-10-23T02:08:10.327729+0 |
| `refs[].doc_id` | 100.0 | 100.0 | string:15 | po_6ad5e518a979 · po_333e1ecbb9df · po_59eb88c08c22 |
| `refs[].doc_number` | 100.0 | 100.0 | string:15 | KSC/PO-00015 · KSC/PO-00016 · KSC/PO-00001 |
| `refs[].doc_type` | 100.0 | 100.0 | string:15 | purchase_order |
| `refs[].note` | 100.0 | 0.0 | string:15 |  |
| `refs[].rel` | 100.0 | 100.0 | string:15 | parent |
| `reject_reason` | 100.0 | 0.0 | string:15 |  |
| `source` | 100.0 | 100.0 | object:15 |  |
| `source.mko_ids` | 100.0 | 0.0 | array:15 |  |
| `source.opened_from` | 100.0 | 100.0 | string:15 | po |
| `source.po_ids` | 100.0 | 100.0 | array:15 |  |
| `status` | 100.0 | 100.0 | string:15 | review · closed · cancelled |
| `updated_at` | 100.0 | 100.0 | string:15 | 2026-10-23T02:07:40.070017+0 · 2026-10-23T02:08:01.462969+0 · 2026-10-23T02:08:10.921092+0 |
| `version` | 100.0 | 100.0 | number:15 | 4 · 10 · 2 |
| `warehouse_id` | 100.0 | 100.0 | string:15 | wh_jakarta |

### `shipments` — 75 dokumen diprofil, 53 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `allocation_id` | 81.3 | 81.3 | string:61 | alloc_db0da99aa21f · alloc_815a156490da · alloc_e99dd894febb |
| `batch_id` | 68.0 | 12.0 | string:51 |  · shb_053493c19f79 |
| `created_at` | 100.0 | 100.0 | string:75 | 2026-10-22T04:17:22.994591+0 · 2026-10-22T04:17:23.167693+0 · 2026-10-22T04:17:25.521761+0 |
| `created_by` | 100.0 | 100.0 | string:75 | Eko Warehouse · Gilang Ramadhan · Fajar Nugroho |
| `customer_id` | 18.7 | 18.7 | string:14 | cust_butik_bali |
| `customer_name` | 18.7 | 18.7 | string:14 | Butik Bali Indah |
| `entity_id` | 100.0 | 100.0 | string:75 | ent_ksc · ent_82b52ed6ee8b · ent_kanda |
| `gl_status` | 81.3 | 81.3 | string:61 | posted |
| `id` | 100.0 | 100.0 | string:75 | shp_7ffb0fe61d3f · shp_7044c9d09733 · shp_5faf8abf7225 |
| `is_partial` | 81.3 | 81.3 | boolean:61 | false · true |
| `kind` | 18.7 | 18.7 | string:14 | cutloss_return · return_back |
| `logistics_id` | 26.7 | 8.0 | string:20 | lgs_454a10228c56 ·  · lgs_8fd0bc0ff4cf |
| `logistics_mode` | 8.0 | 8.0 | string:6 | expedition |
| `logistics_number` | 8.0 | 8.0 | string:6 | KSC/LG-00001 · KSC/LG-00002 · KSC/LG-00003 |
| `logistics_status` | 8.0 | 8.0 | string:6 | delivered |
| `order_id` | 100.0 | 81.3 | string:75 | so_3ee0456e1a42 · so_9a758f00035e · so_5b20e62eb386 |
| `order_number` | 81.3 | 81.3 | string:61 | KSC/SO-00001 · KSC/SO-00002 · CST/SO-00001 |
| `product_id` | 81.3 | 81.3 | string:61 | prod_27f727fa22a1 · prod_aa7a268937b8 · prod_04fdb2ae2bf0 |
| `product_name` | 81.3 | 81.3 | string:61 | DENIM TENCEL TAUPE A · DENIM TENCEL HITAM A · ALICE KNIT (94139 - 45) 14 A |
| `qty` | 81.3 | 81.3 | number:61 | 353.79 · 357.52 · 484.56 |
| `qty_rolls` | 81.3 | 81.3 | number:61 | 3 · 4 · 6 |
| `quantity` | 18.7 | 18.7 | number:14 | 105 · 200 |
| `ref_order_id` | 18.7 | 18.7 | string:14 | so_TEST_U23_aabbfd_8fae · so_TEST_U23_af0d57_023f · so_TEST_U23_25c7d1_a9c0 |
| `ref_order_number` | 18.7 | 18.7 | string:14 | TEST_SO-so_TEST_U23_aabbfd_8 · TEST_SO-so_TEST_U23_af0d57_0 · TEST_SO-so_TEST_U23_25c7d1_a |
| `ref_shipment_id` | 12.0 | 0.0 | string:9 |  |
| `ref_shipment_no` | 12.0 | 0.0 | string:9 |  |
| `refs` | 81.3 | 81.3 | array:61 |  |
| `refs[].at` | 81.3 | 81.3 | string:122 | 2026-10-22T04:17:23.001737+0 · 2026-10-22T04:17:23.008192+0 · 2026-10-22T04:17:23.176536+0 |
| `refs[].doc_id` | 81.3 | 81.3 | string:122 | so_3ee0456e1a42 · wms_c7c34e915279 · wms_eac98f33313a |
| `refs[].doc_number` | 81.3 | 81.3 | string:122 | KSC/SO-00001 · PICK-915279 · PICK-33313A |
| `refs[].doc_type` | 81.3 | 81.3 | string:122 | sales_order · picking_task |
| `refs[].note` | 81.3 | 81.3 | string:122 | pengiriman atas pesanan · dari tugas pengambilan |
| `refs[].rel` | 81.3 | 81.3 | string:122 | parent · fulfills |
| `return_id` | 18.7 | 18.7 | string:14 | sret_TEST_U23_aabbfd_4c5d · sret_TEST_U23_af0d57_34c8 · sret_TEST_U23_25c7d1_395f |
| `return_number` | 18.7 | 18.7 | string:14 | TEST_RET-U23-4c5d · TEST_RET-U23-34c8 · TEST_RET-U23-395f |
| `rolls` | 100.0 | 100.0 | array:75 |  |
| `rolls[].extended_cost` | 81.3 | 81.3 | number:94 | 2069640 · 2125260 · 2173320 |
| `rolls[].length` | 81.3 | 81.3 | number:94 | 114.98 · 118.07 · 120.74 |
| `rolls[].lot` | 81.3 | 81.3 | string:94 | KSC/LOT-2610-0109 · KSC/LOT-2610-0108 · CST/LOT-2610-0003 |
| `rolls[].qty` | 18.7 | 18.7 | number:28 | 45 · 60 · 100 |
| `rolls[].roll_id` | 100.0 | 100.0 | string:122 | roll_af94fc570404 · roll_3767a4801ad4 · roll_047cff3c0d6e |
| `rolls[].roll_no` | 18.7 | 18.7 | string:28 | TEST_RL-U23-037b · TEST_RL-U23-037b-2 · TEST_RL-U23-c817 |
| `rolls[].unit` | 100.0 | 100.0 | string:122 | yard · kg |
| `rolls[].unit_cost` | 81.3 | 81.3 | number:94 | 18000 · 14400 · 28800 |
| `shipment_no` | 100.0 | 100.0 | string:75 | KSC/SJ-00001 · KSC/SJ-00002 · KSC/SJ-00003 |
| `sku` | 81.3 | 81.3 | string:61 | KNWVN0015-L-TAUX-XA-XX-XX · KNWVN0015-L-HTMX-XA-XX-XX · KNKNT0005-I-14XX-XA-XX-XX |
| `status` | 100.0 | 100.0 | string:75 | dispatched |
| `task_id` | 81.3 | 81.3 | string:61 | wms_c7c34e915279 · wms_eac98f33313a · wms_c11d33a8ac54 |
| `unit` | 81.3 | 81.3 | string:61 | yard · kg |
| `updated_at` | 81.3 | 81.3 | string:61 | 2026-10-22T04:17:23.008868+0 · 2026-10-22T04:17:23.184136+0 · 2026-10-22T04:17:25.537276+0 |
| `warehouse_city` | 81.3 | 81.3 | string:61 | Jakarta · Bandung |
| `warehouse_id` | 81.3 | 81.3 | string:61 | wh_jakarta · wh_fe25df27918e · wh_40e831c5bb53 |
| `warehouse_name` | 81.3 | 81.3 | string:61 | Jakarta · Gudang Sukacita · Rancamalang · Gudang Knittin · Soreang · Gudang Kanda |

### `logistics_deliveries` — 6 dokumen diprofil, 71 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `courier_name` | 100.0 | 100.0 | string:6 | LALAMOVE · JNE |
| `created_at` | 100.0 | 100.0 | string:6 | 2026-10-22T06:45:45.938550+0 · 2026-10-25T05:24:19.192635+0 · 2026-10-25T05:24:21.271365+0 |
| `created_by` | 100.0 | 100.0 | string:6 | Budi Santoso · Hendra Kepala Gudang |
| `customer_id` | 100.0 | 100.0 | string:6 | cust_butik_bali · cust_toko_kain |
| `customer_name` | 100.0 | 100.0 | string:6 | Butik Bali Indah · Toko Kain Sejahtera |
| `delivered_at` | 100.0 | 100.0 | string:6 | 2026-10-22T06:47:18.398418+0 · 2026-10-25T05:24:19.381830+0 · 2026-10-25T05:24:21.389534+0 |
| `departed_at` | 100.0 | 100.0 | string:6 | 2026-10-22T06:46:40.363802+0 · 2026-10-25T05:24:19.295056+0 · 2026-10-25T05:24:21.343807+0 |
| `destination` | 100.0 | 100.0 | string:6 | Ibu Komang, Jl. Seminyak No. · Pak Hendra, Jl. Mangga Besar |
| `driver_name` | 100.0 | 0.0 | string:6 |  |
| `driver_user_id` | 100.0 | 0.0 | string:6 |  |
| `entity_id` | 100.0 | 100.0 | string:6 | ent_ksc |
| `eta` | 100.0 | 16.7 | string:6 | 2026-10-24 ·  |
| `fail_reason` | 100.0 | 0.0 | string:6 |  |
| `fulfillment_method` | 100.0 | 100.0 | string:6 | kirim |
| `id` | 100.0 | 100.0 | string:6 | lgs_454a10228c56 · lgs_8fd0bc0ff4cf · lgs_2a547318ab59 |
| `is_multi_order` | 100.0 | 100.0 | boolean:6 | false |
| `loaded_at` | 100.0 | 100.0 | string:6 | 2026-10-22T06:46:34.944388+0 · 2026-10-25T05:24:19.268385+0 · 2026-10-25T05:24:21.319884+0 |
| `mode` | 100.0 | 100.0 | string:6 | expedition |
| `notes` | 100.0 | 0.0 | string:6 |  |
| `number` | 100.0 | 100.0 | string:6 | KSC/LG-00001 · KSC/LG-00002 · KSC/LG-00003 |
| `order_id` | 100.0 | 100.0 | string:6 | so_02bb630a3110 · so_854aa6b2bc83 · so_7fe3fb8b1d2c |
| `order_ids` | 100.0 | 100.0 | array:6 |  |
| `order_number` | 100.0 | 100.0 | string:6 | KSC/SO-00005 · KSC/SO-00424 · KSC/SO-00425 |
| `orders` | 100.0 | 100.0 | array:6 |  |
| `orders[].customer_id` | 100.0 | 100.0 | string:6 | cust_butik_bali · cust_toko_kain |
| `orders[].customer_name` | 100.0 | 100.0 | string:6 | Butik Bali Indah · Toko Kain Sejahtera |
| `orders[].destination` | 100.0 | 100.0 | string:6 | Ibu Komang, Jl. Seminyak No. · Pak Hendra, Jl. Mangga Besar |
| `orders[].order_id` | 100.0 | 100.0 | string:6 | so_02bb630a3110 · so_854aa6b2bc83 · so_7fe3fb8b1d2c |
| `orders[].order_number` | 100.0 | 100.0 | string:6 | KSC/SO-00005 · KSC/SO-00424 · KSC/SO-00425 |
| `orders[].shipment_ids` | 100.0 | 100.0 | array:6 |  |
| `orders[].shipment_nos` | 100.0 | 100.0 | array:6 |  |
| `photos` | 100.0 | 100.0 | array:6 |  |
| `photos[].at` | 100.0 | 100.0 | string:12 | 2026-10-22T06:45:57.748332+0 · 2026-10-22T06:47:12.933319+0 · 2026-10-25T05:24:19.240167+0 |
| `photos[].by` | 100.0 | 100.0 | string:12 | Budi Santoso · Hendra Kepala Gudang |
| `photos[].content_type` | 100.0 | 100.0 | string:12 | image/jpeg · image/png |
| `photos[].filename` | 100.0 | 100.0 | string:12 | 751b5aa02bb528542d0fc15d0b08 · load.png · pod.png |
| `photos[].id` | 100.0 | 100.0 | string:12 | pho_c121482a4800 · pho_74985d633287 · pho_94de98731143 |
| `photos[].kind` | 100.0 | 100.0 | string:12 | load · pod |
| `photos[].note` | 100.0 | 83.3 | string:12 |  · uji F-06 |
| `photos[].path` | 100.0 | 100.0 | string:12 | kn7/logistics/b7f8c0d489b74d · kn7/logistics/a82f80cbd4104f · kn7/logistics/25f491fcf72245 |
| `photos[].size` | 100.0 | 100.0 | number:12 | 20796 · 67 |
| `pickup_attempts` | 100.0 | 100.0 | number:6 | 0 |
| `pickup_code` | 100.0 | 0.0 | string:6 |  |
| `pickup_date` | 100.0 | 0.0 | string:6 |  |
| `pod` | 100.0 | 100.0 | object:6 |  |
| `pod.at` | 100.0 | 100.0 | string:6 | 2026-10-22T06:47:18.398412+0 · 2026-10-25T05:24:19.381825+0 · 2026-10-25T05:24:21.389528+0 |
| `pod.by` | 100.0 | 100.0 | string:6 | Budi Santoso · Hendra Kepala Gudang |
| `pod.note` | 100.0 | 0.0 | string:6 |  |
| `pod.received_at` | 100.0 | 100.0 | string:6 | 2026-10-22T06:47:18.398407+0 · 2026-10-25T05:24:19.381821+0 · 2026-10-25T05:24:21.389522+0 |
| `pod.receiver_name` | 100.0 | 100.0 | string:6 | Ibu Komang · Bu Rina (uji F-06) |
| `positions` | 100.0 | 0.0 | array:6 |  |
| `receiver_name_hint` | 100.0 | 100.0 | string:6 | Ibu Komang · Pak Hendra |
| `receiver_phone` | 100.0 | 100.0 | string:6 | 6282345678901 · 6281234567890 |
| `service_level` | 100.0 | 16.7 | string:6 | instant ·  |
| `shipment_ids` | 100.0 | 100.0 | array:6 |  |
| `shipment_nos` | 100.0 | 100.0 | array:6 |  |
| `shipping_cost` | 100.0 | 100.0 | number:6 | 0 |
| `status` | 100.0 | 100.0 | string:6 | delivered |
| `timeline` | 100.0 | 100.0 | array:6 |  |
| `timeline[].action` | 100.0 | 100.0 | string:39 | created · photo · updated |
| `timeline[].at` | 100.0 | 100.0 | string:39 | 2026-10-22T06:45:45.938532+0 · 2026-10-22T06:45:57.748410+0 · 2026-10-22T06:46:14.067967+0 |
| `timeline[].by` | 100.0 | 100.0 | string:39 | Budi Santoso · Hendra Kepala Gudang |
| `timeline[].from_status` | 100.0 | 100.0 | string:18 | prepared · loaded · in_transit |
| `timeline[].id` | 100.0 | 100.0 | string:39 | evt_c06f599e0abb · evt_4d9e2ab83094 · evt_e67c8e2e03bd |
| `timeline[].kind` | 100.0 | 100.0 | string:13 | load · pod |
| `timeline[].note` | 100.0 | 100.0 | string:39 | Pengiriman disiapkan · Foto muat · Bukti terima (POD) |
| `timeline[].to_status` | 100.0 | 100.0 | string:18 | loaded · in_transit · delivered |
| `tracking_no` | 100.0 | 100.0 | string:6 | 123123 · RESI-F06-UJI |
| `updated_at` | 100.0 | 100.0 | string:6 | 2026-10-22T06:47:18.398374+0 · 2026-10-25T05:24:19.381793+0 · 2026-10-25T05:24:21.389486+0 |
| `vehicle_id` | 100.0 | 0.0 | string:6 |  |
| `vehicle_plate` | 100.0 | 0.0 | string:6 |  |

### `rfid_tags` — 41 dokumen diprofil, 22 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `activated_at` | 34.1 | 34.1 | string:14 | 2026-10-23T17:48:15.295755+0 · 2026-10-23T17:48:18.674561+0 · 2026-10-23T19:07:02.721542+0 |
| `encoded_at` | 100.0 | 100.0 | string:41 | 2026-10-22T06:19:25.109969+0 · 2026-10-22T06:21:20.637237+0 · 2026-10-22T06:21:26.041318+0 |
| `encoded_by` | 100.0 | 100.0 | string:41 | Budi Santoso · Eko Warehouse · Hendra Kepala Gudang |
| `epc` | 100.0 | 100.0 | string:41 | E276D971960269459CB99D27 · E24E1A9A7DE24D4375957787 · E21FC12E4BE9A24E9BA525F4 |
| `id` | 100.0 | 100.0 | string:41 | rtag_3bd08b08a9e2 · rtag_e553b7417592 · rtag_9d0f44bb3325 |
| `last_seen_at` | 100.0 | 2.4 | null:40, string:1 | 2026-11-03T21:49:51.920422+0 |
| `last_seen_device_id` | 100.0 | 2.4 | null:40, string:1 | rdev_891088a797f4 |
| `last_seen_device_name` | 100.0 | 2.4 | null:40, string:1 | UJI-CELUP gate-out |
| `last_seen_location` | 100.0 | 0.0 | null:40, string:1 |  |
| `last_seen_warehouse_id` | 100.0 | 2.4 | null:40, string:1 | wh_jakarta |
| `lot` | 100.0 | 97.6 | string:41 |  · a · LOT-001 |
| `owner_entity_id` | 100.0 | 100.0 | string:41 | ent_ksc |
| `product_id` | 100.0 | 100.0 | string:41 | prod_lurik_classic · prod_ulos_batak · prod_84f470317401 |
| `product_name` | 100.0 | 100.0 | string:41 | Lurik Klasik Solo · Ulos Batak Ragidup · Rayon motif kawung navy — SO |
| `retire_reason` | 14.6 | 14.6 | string:6 | roll_dibatalkan |
| `retired_at` | 14.6 | 14.6 | string:6 | 2026-10-22T06:19:33.662727+0 · 2026-10-22T06:21:46.545396+0 · 2026-10-22T06:21:46.880422+0 |
| `roll_id` | 100.0 | 100.0 | string:41 | roll_9e74d7987365 · roll_ac4a623b0e37 · roll_bc6450d4c9f1 |
| `roll_no` | 100.0 | 100.0 | string:41 | RL-46516 · RL-46517 · RL-46518 |
| `simulated` | 17.1 | 17.1 | boolean:7 | true |
| `sku` | 100.0 | 100.0 | string:41 | LRK-CLSC-001 · ULS-BTK-001 · RND-SPEC-00018 |
| `status` | 100.0 | 100.0 | string:41 | retired · active |
| `warehouse_id` | 100.0 | 100.0 | string:41 | wh_09155c408ab2 · wh_jakarta · wh_adc8726d019e |

### `rfid_reads` — 1 dokumen diprofil, 29 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `action` | 100.0 | 100.0 | string:1 | Loloskan — cocokkan jumlah r |
| `code` | 100.0 | 100.0 | string:1 | MOVEMENT_OUT |
| `device_id` | 100.0 | 100.0 | string:1 | rdev_891088a797f4 |
| `device_name` | 100.0 | 100.0 | string:1 | UJI-CELUP gate-out |
| `device_type` | 100.0 | 100.0 | string:1 | gate |
| `epc` | 100.0 | 100.0 | string:1 | E20338E3B9999847319242C4 |
| `id` | 100.0 | 100.0 | string:1 | rread_robs_f788a93de7d1 |
| `last_observed_at` | 100.0 | 100.0 | string:1 | 2026-11-03T21:49:53.044139+0 |
| `location` | 100.0 | 0.0 | string:1 |  |
| `movement` | 100.0 | 100.0 | object:1 |  |
| `movement.dest_wh` | 100.0 | 0.0 | null:1 |  |
| `movement.id` | 100.0 | 100.0 | string:1 | mko_e446a412810a:1 |
| `movement.number` | 100.0 | 100.0 | string:1 | KSC/MKO-00081 langkah 1 |
| `movement.source_wh` | 100.0 | 100.0 | string:1 | wh_jakarta |
| `movement.type` | 100.0 | 100.0 | string:1 | makloon_order |
| `observation_count` | 100.0 | 100.0 | number:1 | 2 |
| `owner_entity_id` | 100.0 | 100.0 | string:1 | ent_ksc |
| `passage_id` | 100.0 | 100.0 | string:1 | rpsg_fde96e90f173 |
| `product_name` | 100.0 | 100.0 | string:1 | CHIKITA KNIT BEIGE A LOT B |
| `read_type` | 100.0 | 100.0 | string:1 | gate_out |
| `reason` | 100.0 | 100.0 | string:1 | Keluar ter-otorisasi untuk K |
| `result` | 100.0 | 100.0 | string:1 | green |
| `roll_id` | 100.0 | 100.0 | string:1 | roll_671835018f02 |
| `roll_no` | 100.0 | 100.0 | string:1 | RL-04999 |
| `sku` | 100.0 | 100.0 | string:1 | KNKNT0021-L-BEIX-XA-XX-XB |
| `source` | 100.0 | 100.0 | string:1 | simulated |
| `tag_id` | 100.0 | 100.0 | string:1 | rtag_3c679a8940b8 |
| `timestamp` | 100.0 | 100.0 | string:1 | 2026-11-03T21:49:51.920422+0 |
| `warehouse_id` | 100.0 | 100.0 | string:1 | wh_jakarta |

### `rfid_devices` — 1 dokumen diprofil, 13 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `code` | 100.0 | 100.0 | string:1 | DEV-84134 |
| `created_at` | 100.0 | 100.0 | string:1 | 2026-11-03T21:49:51.884973+0 |
| `created_by` | 100.0 | 100.0 | string:1 | Budi Santoso |
| `direction` | 100.0 | 100.0 | string:1 | out |
| `enabled` | 100.0 | 100.0 | boolean:1 | true |
| `id` | 100.0 | 100.0 | string:1 | rdev_891088a797f4 |
| `last_heartbeat` | 100.0 | 100.0 | string:1 | 2026-11-03T21:49:53.042851+0 |
| `location` | 100.0 | 0.0 | string:1 |  |
| `name` | 100.0 | 100.0 | string:1 | UJI-CELUP gate-out |
| `status` | 100.0 | 100.0 | string:1 | online |
| `type` | 100.0 | 100.0 | string:1 | gate |
| `warehouse_id` | 100.0 | 100.0 | string:1 | wh_jakarta |
| `warehouse_name` | 100.0 | 100.0 | string:1 | Jakarta · Gudang Sukacita |

### `rfid_passages` — 1 dokumen diprofil, 14 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `acknowledged_at` | 100.0 | 0.0 | null:1 |  |
| `device_id` | 100.0 | 100.0 | string:1 | rdev_891088a797f4 |
| `device_name` | 100.0 | 100.0 | string:1 | UJI-CELUP gate-out |
| `direction` | 100.0 | 100.0 | string:1 | out |
| `epcs` | 100.0 | 100.0 | array:1 |  |
| `green_count` | 100.0 | 100.0 | number:1 | 1 |
| `id` | 100.0 | 100.0 | string:1 | rpsg_fde96e90f173 |
| `info_count` | 100.0 | 100.0 | number:1 | 0 |
| `last_at` | 100.0 | 100.0 | string:1 | 2026-11-03T21:49:53.044139+0 |
| `read_ids` | 100.0 | 100.0 | array:1 |  |
| `red_count` | 100.0 | 100.0 | number:1 | 0 |
| `started_at` | 100.0 | 100.0 | string:1 | 2026-11-03T21:49:51.920422+0 |
| `verdict` | 100.0 | 100.0 | string:1 | green |
| `warehouse_id` | 100.0 | 100.0 | string:1 | wh_jakarta |

### `rfid_observations` — 2 dokumen diprofil, 10 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `antenna` | 100.0 | 0.0 | null:2 |  |
| `batch_id` | 100.0 | 0.0 | null:2 |  |
| `captured_at` | 100.0 | 0.0 | null:2 |  |
| `device_id` | 100.0 | 100.0 | string:2 | rdev_891088a797f4 |
| `epc` | 100.0 | 100.0 | string:2 | E20338E3B9999847319242C4 |
| `event_id` | 100.0 | 0.0 | null:2 |  |
| `processed` | 100.0 | 100.0 | boolean:2 | true |
| `received_at` | 100.0 | 100.0 | string:2 | 2026-11-03T21:49:51.920422+0 · 2026-11-03T21:49:53.044139+0 |
| `rssi` | 100.0 | 0.0 | null:2 |  |
| `source` | 100.0 | 100.0 | string:2 | simulated |

### `rfid_print_jobs` — 8 dokumen diprofil, 30 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `created_at` | 100.0 | 100.0 | string:8 | 2026-10-23T17:48:15.101365+0 · 2026-10-23T17:48:18.648335+0 · 2026-10-23T19:07:02.628372+0 |
| `created_by` | 100.0 | 100.0 | string:8 | Budi Santoso |
| `id` | 100.0 | 100.0 | string:8 | rpj_01f2e6a14a87 · rpj_7b4fb21fc4b9 · rpj_a358acd053a3 |
| `item_count` | 100.0 | 100.0 | number:8 | 2 · 3 |
| `items` | 100.0 | 100.0 | array:8 |  |
| `items[].epc` | 100.0 | 100.0 | string:20 | E2F22BECFEDF8B47BCB4524C · E2F6FF878012AF4A52ACDF70 · E2CE437A4452914BA1947471 |
| `items[].lot` | 100.0 | 100.0 | string:20 | LOT-001 · LOT-002 · KSC/LOT-2610-0008 |
| `items[].product_name` | 100.0 | 100.0 | string:20 | Batik Mega Mendung Premium · Tenun Ikat Garuda Premium · Ulos Batak Ragidup |
| `items[].qty` | 100.0 | 100.0 | number:20 | 50 · 150 · 120 |
| `items[].reprint` | 100.0 | 100.0 | boolean:20 | false |
| `items[].roll_id` | 100.0 | 100.0 | string:20 | roll_4bffd67fe1b2 · roll_ef29cb4553f3 · roll_da2d8b960bf8 |
| `items[].roll_no` | 100.0 | 100.0 | string:20 | RL-00005 · RL-00006 · RL-00007 |
| `items[].sku` | 100.0 | 100.0 | string:20 | BTK-MEGA-001 · TNI-GRGD-001 · ULS-BTK-001 |
| `items[].tag_id` | 100.0 | 100.0 | string:20 | rtag_de19f89792f2 · rtag_34342c7e0282 · rtag_d34c9e208f6d |
| `items[].unit` | 100.0 | 100.0 | string:20 | yard · kg |
| `items[].zpl` | 100.0 | 100.0 | string:20 | ^XA ^CI28 ^RS8 ^RFW,H^FDE2F2 · ^XA ^CI28 ^RS8 ^RFW,H^FDE2F6 · ^XA ^CI28 ^RS8 ^RFW,H^FDE2CE |
| `job_number` | 100.0 | 100.0 | string:8 | PJ00001 · PJ00002 · PJ00003 |
| `kind` | 100.0 | 100.0 | string:8 | rfid_tag |
| `last_verify` | 100.0 | 100.0 | object:8 |  |
| `last_verify.at` | 100.0 | 100.0 | string:8 | 2026-10-23T17:48:15.506406+0 · 2026-10-23T17:48:18.740544+0 · 2026-10-23T19:07:02.839666+0 |
| `last_verify.result` | 100.0 | 100.0 | string:8 | with_issues · clean |
| `last_verify.session_id` | 100.0 | 100.0 | string:8 | rvs_1bc2553cc7cc · rvs_2f2195daff4e · rvs_297f9d711f89 |
| `owner_entity_id` | 100.0 | 100.0 | string:8 | ent_ksc |
| `printed_at` | 100.0 | 100.0 | string:8 | 2026-10-23T17:48:15.269354+0 · 2026-10-23T17:48:18.663575+0 · 2026-10-23T19:07:02.710383+0 |
| `printed_via` | 100.0 | 100.0 | string:8 | manual |
| `status` | 100.0 | 100.0 | string:8 | verified_with_issues · verified |
| `updated_at` | 100.0 | 100.0 | string:8 | 2026-10-23T17:48:15.506425+0 · 2026-10-23T17:48:18.740554+0 · 2026-10-23T19:07:02.839678+0 |
| `verified_at` | 100.0 | 100.0 | string:8 | 2026-10-23T17:48:15.506422+0 · 2026-10-23T17:48:18.740552+0 · 2026-10-23T19:07:02.839676+0 |
| `warehouse_id` | 100.0 | 100.0 | string:8 | wh_jakarta · wh_5ae35dcd8837 |
| `warehouse_name` | 100.0 | 100.0 | string:8 | Jakarta · Gudang Sukacita · Rancamalang · Gudang Transit |

### `rfid_verify_sessions` — 11 dokumen diprofil, 38 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `completed_at` | 100.0 | 100.0 | string:11 | 2026-10-22T06:41:03.175957+0 · 2026-10-22T06:45:09.954543+0 · 2026-10-22T10:38:14.249312+0 |
| `created_at` | 100.0 | 100.0 | string:11 | 2026-10-22T06:40:54.520860+0 · 2026-10-22T06:45:05.294808+0 · 2026-10-22T10:38:08.784872+0 |
| `created_by` | 100.0 | 100.0 | string:11 | Eko Warehouse · Budi Santoso |
| `expected` | 100.0 | 100.0 | array:11 |  |
| `expected[].epc` | 100.0 | 100.0 | string:29 | E2CA604CBF4BE94AB0B09A65 · E23FBBF0144D754A45BF6C9A · E206409EEC5565484280DFA2 |
| `expected[].product_name` | 100.0 | 100.0 | string:29 | Lurik Klasik Solo · Ulos Batak Ragidup · Batik Mega Mendung Premium |
| `expected[].roll_id` | 100.0 | 100.0 | string:29 | roll_08a02ac91ac8 · roll_ef4043071f86 · roll_242b638b7dbb |
| `expected[].roll_no` | 100.0 | 100.0 | string:29 | RL-00008 · RL-00009 · RL-00010 |
| `expected[].sku` | 100.0 | 100.0 | string:29 | LRK-CLSC-001 · ULS-BTK-001 · BTK-MEGA-001 |
| `extra` | 100.0 | 36.4 | array:11 |  |
| `id` | 100.0 | 100.0 | string:11 | rvs_c9493385fbca · rvs_1675ecd16ce7 · rvs_7b96050075ba |
| `job_number` | 72.7 | 72.7 | string:8 | PJ00001 · PJ00002 · PJ00003 |
| `kind` | 100.0 | 100.0 | string:11 | loading_check · print_verify |
| `missing` | 100.0 | 0.0 | array:11 |  |
| `not_committed_count` | 27.3 | 27.3 | number:3 | 0 · 1 |
| `order_id` | 27.3 | 27.3 | string:3 | so_02bb630a3110 · so_455c73aa8ef7 |
| `owner_entity_id` | 100.0 | 100.0 | string:11 | ent_ksc |
| `print_job_id` | 100.0 | 72.7 | null:3, string:8 | rpj_01f2e6a14a87 · rpj_7b4fb21fc4b9 · rpj_a358acd053a3 |
| `result` | 100.0 | 100.0 | string:11 | simulated · with_issues · clean |
| `revision` | 72.7 | 72.7 | number:8 | 1 |
| `scan_log` | 100.0 | 100.0 | array:11 |  |
| `scan_log[].at` | 100.0 | 100.0 | string:19 | 2026-10-22T06:41:00.973547+0 · 2026-10-22T06:45:07.426885+0 · 2026-10-22T10:38:11.228717+0 |
| `scan_log[].by` | 100.0 | 100.0 | string:19 | Eko Warehouse · Budi Santoso |
| `scan_log[].count` | 100.0 | 100.0 | number:19 | 6 · 2 · 1 |
| `scan_log[].device_id` | 100.0 | 0.0 | null:19 |  |
| `scan_log[].device_name` | 100.0 | 0.0 | null:19 |  |
| `scan_log[].epcs` | 100.0 | 100.0 | array:19 |  |
| `scan_log[].source` | 100.0 | 100.0 | string:19 | simulated · manual |
| `scan_sources` | 100.0 | 100.0 | array:11 |  |
| `scanned_epcs` | 100.0 | 100.0 | array:11 |  |
| `simulated_epcs` | 27.3 | 27.3 | array:3 |  |
| `so_number` | 27.3 | 27.3 | string:3 | KSC/SO-00005 · KSC/SOS-00001 |
| `status` | 100.0 | 100.0 | string:11 | completed |
| `untagged` | 27.3 | 0.0 | array:3 |  |
| `untagged_count` | 27.3 | 27.3 | number:3 | 0 |
| `untagged_resolved` | 27.3 | 0.0 | array:3 |  |
| `updated_at` | 100.0 | 100.0 | string:11 | 2026-10-22T06:41:00.973518+0 · 2026-10-22T06:45:07.426858+0 · 2026-10-22T10:38:11.228693+0 |
| `warehouse_id` | 100.0 | 100.0 | string:11 | wh_jakarta · wh_09155c408ab2 · wh_5ae35dcd8837 |

### `roll_label_prints` — 20 dokumen diprofil, 15 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `at` | 100.0 | 100.0 | string:20 | 2026-10-23T17:48:15.273241+0 · 2026-10-23T17:48:15.293295+0 · 2026-10-23T17:48:18.666796+0 |
| `by` | 100.0 | 100.0 | string:20 | Budi Santoso |
| `channel` | 100.0 | 100.0 | string:20 | print_queue |
| `epc` | 100.0 | 100.0 | string:20 | E2F22BECFEDF8B47BCB4524C · E2F6FF878012AF4A52ACDF70 · E2CE437A4452914BA1947471 |
| `id` | 100.0 | 100.0 | string:20 | rlp_c60d3856a93f · rlp_85f9970eda7c · rlp_1e8b0f57176d |
| `job_id` | 100.0 | 100.0 | string:20 | rpj_01f2e6a14a87 · rpj_7b4fb21fc4b9 · rpj_a358acd053a3 |
| `job_number` | 100.0 | 100.0 | string:20 | PJ00001 · PJ00002 · PJ00003 |
| `kind` | 100.0 | 100.0 | string:20 | rfid_tag |
| `owner_entity_id` | 100.0 | 100.0 | string:20 | ent_ksc |
| `print_seq` | 100.0 | 100.0 | number:20 | 1 |
| `qty` | 100.0 | 100.0 | number:20 | 50 · 150 · 120 |
| `reprint` | 100.0 | 100.0 | boolean:20 | false |
| `roll_id` | 100.0 | 100.0 | string:20 | roll_4bffd67fe1b2 · roll_ef29cb4553f3 · roll_da2d8b960bf8 |
| `roll_no` | 100.0 | 100.0 | string:20 | RL-00005 · RL-00006 · RL-00007 |
| `unit` | 100.0 | 100.0 | string:20 | yard · kg |

### `inspections` — 113 dokumen diprofil, 214 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `assigned_name` | 100.0 | 32.7 | string:113 | Mulyadi · Budi Santoso ·  |
| `assigned_to` | 100.0 | 32.7 | string:113 | user_03f0d6ed87f7 · user_admin_01 ·  |
| `bagian` | 100.0 | 100.0 | string:113 | QC · Bagian Inspect · Bagian Inspeksi |
| `baseline_color` | 100.0 | 0.0 | string:113 |  |
| `baseline_contract_id` | 100.0 | 1.8 | string:113 |  · sct_3faf9d94a718 · sct_dec1ff444cd9 |
| `baseline_round_no` | 1.8 | 1.8 | number:2 | 1 |
| `baseline_sample_id` | 100.0 | 1.8 | string:113 |  · smp_7f562433dbec · smp_83f11b9d390d |
| `baseline_sample_number` | 100.0 | 1.8 | string:113 |  · KSC/SMP-00018 · KSC/SMP-00017 |
| `baseline_supplier_id` | 1.8 | 1.8 | string:2 | sup_a47057e2dfc2 |
| `created_at` | 100.0 | 100.0 | string:113 | 2026-10-22T04:17:18.096107+0 · 2026-10-22T18:44:16.471399+0 · 2026-10-22T18:53:29.818667+0 |
| `created_by` | 100.0 | 100.0 | string:113 | Gilang Ramadhan · Dewi Manager · Eko Warehouse |
| `created_by_id` | 100.0 | 87.6 | string:113 | user_d016b4951468 · user_manager_01 · user_wh_01 |
| `customer_id` | 100.0 | 51.3 | string:113 |  · cust_toko_kain · cust_butik_bali |
| `customer_name` | 100.0 | 51.3 | string:113 |  · Toko Kain Sejahtera · Butik Bali Indah |
| `decided_at` | 38.1 | 38.1 | string:43 | 2026-10-22T04:17:19.106474+0 · 2026-10-22T18:50:28.933092+0 · 2026-10-22T18:53:30.393040+0 |
| `decided_by` | 38.1 | 38.1 | string:43 | Mulyadi · Budi Santoso · Uji F2 |
| `decision` | 100.0 | 38.1 | string:113 | terima · terima_sebagian · tolak |
| `decision_label` | 100.0 | 38.1 | string:113 | Diterima seluruhnya · Diterima sebagian · Ditolak |
| `entity_id` | 100.0 | 100.0 | string:113 | ent_82b52ed6ee8b · ent_ksc |
| `excluded_lines` | 10.6 | 10.6 | array:12 |  |
| `excluded_lines[].article` | 10.6 | 10.6 | string:24 | Batik Mega Mendung Premium · Produk Uji F2 080291 · Produk Uji F2 fb26be |
| `excluded_lines[].color_code` | 10.6 | 5.3 | string:24 |  · KN-SJT-01 |
| `excluded_lines[].color_id` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].color_result` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].decision` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].delta_e` | 10.6 | 0.0 | null:24 |  |
| `excluded_lines[].dye_lot` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].excluded_at` | 10.6 | 10.6 | string:24 | 2026-10-23T18:10:48.881294+0 · 2026-10-23T18:10:48.881303+0 · 2026-10-23T18:11:49.013003+0 |
| `excluded_lines[].excluded_reason` | 10.6 | 10.6 | string:24 | tidak diperiksa (sampling) |
| `excluded_lines[].grade_after` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].grade_before` | 10.6 | 10.6 | string:24 | A |
| `excluded_lines[].gsm_actual` | 10.6 | 0.0 | null:24 |  |
| `excluded_lines[].gsm_standard` | 10.6 | 10.6 | number:24 | 120 |
| `excluded_lines[].handfeel_result` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].handfeel_score` | 10.6 | 0.0 | null:24 |  |
| `excluded_lines[].hold` | 10.6 | 10.6 | boolean:24 | false |
| `excluded_lines[].hold_reason` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].id` | 10.6 | 10.6 | string:24 | insl_5c3bd71c44a3 · insl_828f2361f28e · insl_e04e576f8c65 |
| `excluded_lines[].inspected_at` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].inspected_by` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].lot` | 10.6 | 10.6 | string:24 | LOT-F2-887160 · LOT-F2-d473eb · LOT-F2-03fa86 |
| `excluded_lines[].points_snapshot` | 10.6 | 0.0 | null:24 |  |
| `excluded_lines[].product_id` | 10.6 | 10.6 | string:24 | prod_batik_mega · prod_TEST_F2_080291 · prod_TEST_F2_fb26be |
| `excluded_lines[].qty_rolls` | 10.6 | 10.6 | number:24 | 1 |
| `excluded_lines[].quantity` | 10.6 | 10.6 | number:24 | 50 |
| `excluded_lines[].remark` | 10.6 | 0.0 | string:24 |  |
| `excluded_lines[].roll_id` | 10.6 | 10.6 | string:24 | roll_TEST_F2_887160_qc1 · roll_TEST_F2_887160_qc2 · roll_TEST_F2_d473eb_qc1 |
| `excluded_lines[].roll_no` | 10.6 | 10.6 | string:24 | TF2887160QC1 · TF2887160QC2 · TF2D473EBQC1 |
| `excluded_lines[].sku` | 10.6 | 10.6 | string:24 | BTK-MEGA-001 · TST-F2-080291 · TST-F2-fb26be |
| `excluded_lines[].unit` | 10.6 | 10.6 | string:24 | yard |
| `excluded_lines[].width_actual` | 10.6 | 0.0 | null:24 |  |
| `excluded_lines[].width_standard` | 10.6 | 10.6 | number:24 | 1.15 |
| `finished_at` | 100.0 | 38.1 | string:113 | 2026-10-22T04:17:19.106471+0 · 2026-10-22T18:50:28.933075+0 · 2026-10-22T18:53:30.393033+0 |
| `history` | 100.0 | 100.0 | array:113 |  |
| `history[].actor` | 100.0 | 100.0 | string:322 | Gilang Ramadhan · Hana Safitri · Mulyadi |
| `history[].at` | 100.0 | 100.0 | string:322 | 2026-10-22T04:17:18.100008+0 · 2026-10-22T04:17:18.736694+0 · 2026-10-22T04:17:18.766069+0 |
| `history[].event` | 100.0 | 100.0 | string:322 | created · assigned · started |
| `history[].label` | 100.0 | 100.0 | string:322 | Inspeksi Penerimaan PO dibua · Ditugaskan ke Mulyadi · Pemeriksaan dimulai |
| `history[].note` | 100.0 | 89.4 | string:322 | CST/PO-00001 · QC ·  |
| `id` | 100.0 | 100.0 | string:113 | ins_22ba2e8da9a3 · ins_99b9c00525b0 · ins_1b054e96b840 |
| `kind` | 100.0 | 100.0 | string:113 | po_receipt · return_customer · random_check |
| `line_code` | 100.0 | 9.7 | string:113 |  · woven · printing |
| `lines` | 100.0 | 100.0 | array:113 |  |
| `lines[].actual_qty` | 0.9 | 0.9 | number:2 | 60.5 · 20 |
| `lines[].article` | 100.0 | 99.1 | string:155 | Benang Katun 30s (untuk Tenu · ATHENA STRETCH WHITECAP GREY · Grey Woven Katun Poplin |
| `lines[].claim` | 49.6 | 49.6 | object:58 |  |
| `lines[].color_code` | 100.0 | 67.3 | string:155 |  · 11 · CRMX |
| `lines[].color_id` | 100.0 | 0.0 | string:155 |  |
| `lines[].color_result` | 100.0 | 23.9 | string:155 |  · sesuai · beda_shade |
| `lines[].condition` | 0.9 | 0.9 | string:2 | ok · minor |
| `lines[].decision` | 100.0 | 9.7 | string:155 |  · tolak · terima |
| `lines[].defects` | 8.8 | 8.0 | array:19 |  |
| `lines[].delta_e` | 100.0 | 0.0 | null:155 |  |
| `lines[].dye_lot` | 100.0 | 87.6 | string:155 | DM-DL-9A129A · KSC/LOT-2610-0096 · F14-DL-D782A8 |
| `lines[].grade_after` | 100.0 | 8.8 | string:155 | A · B ·  |
| `lines[].grade_before` | 100.0 | 98.2 | string:155 | A ·  · A1 |
| `lines[].grade_rule` | 8.8 | 8.8 | object:19 |  |
| `lines[].gsm_actual` | 100.0 | 0.0 | null:155 |  |
| `lines[].gsm_standard` | 100.0 | 98.2 | number:153, null:2 | 0 · 192 · 110 |
| `lines[].handfeel_result` | 100.0 | 23.9 | string:155 |  · sesuai |
| `lines[].handfeel_score` | 100.0 | 0.0 | null:155 |  |
| `lines[].hold` | 100.0 | 100.0 | boolean:155 | false · true |
| `lines[].hold_reason` | 100.0 | 3.5 | string:155 |  · Warna beda dari sample yang  · Random check GAGAL — roll te |
| `lines[].hold_release_reason` | 1.8 | 1.8 | string:2 | pelanggan setuju shade sedik |
| `lines[].hold_released_at` | 1.8 | 1.8 | string:2 | 2026-10-22T18:53:55.704084+0 · 2026-10-23T17:56:34.609723+0 |
| `lines[].hold_released_by` | 1.8 | 1.8 | string:2 | Budi Santoso |
| `lines[].id` | 100.0 | 100.0 | string:155 | insl_2c093e704f25 · insl_e0ec8969c779 · insl_5107e65c5ddd |
| `lines[].inspect_form` | 8.8 | 8.8 | object:19 |  |
| `lines[].inspected_at` | 100.0 | 43.4 | string:155 | 2026-10-22T04:17:18.787522+0 · 2026-10-22T18:47:33.802723+0 · 2026-10-22T18:48:34.767343+0 |
| `lines[].inspected_by` | 100.0 | 32.7 | string:155 | Mulyadi · Lestari Wulandari · Budi Santoso |
| `lines[].lot` | 100.0 | 98.2 | string:155 | CST/LOT-2610-0202 · KSC/LOT-2610-0096 · KSC/LOT-2610-0135 |
| `lines[].md_quality_at` | 23.9 | 23.9 | string:59 | 2026-10-22T18:53:29.985550+0 · 2026-10-22T18:53:30.047657+0 · 2026-10-22T18:53:30.142156+0 |
| `lines[].md_quality_by` | 23.9 | 23.9 | string:59 | Lestari Wulandari · Budi Santoso |
| `lines[].md_quality_decision` | 1.8 | 1.8 | object:2 |  |
| `lines[].md_remark` | 23.9 | 22.1 | string:59 | uji F-14 bersih ·  · OD uji — sesuai sample |
| `lines[].points_snapshot` | 100.0 | 8.8 | number:19, null:136 | 0 · 2 · 6 |
| `lines[].product_id` | 100.0 | 100.0 | string:155 | prod_cc00b3aed90e · prod_c37e5ec87565 · prod_97ef39b63081 |
| `lines[].qc4_result` | 15.9 | 15.9 | string:24 | ditahan · lulus |
| `lines[].qc_at` | 19.5 | 19.5 | string:31 | 2026-10-22T04:17:18.787537+0 · 2026-10-22T18:47:33.802746+0 · 2026-10-22T18:48:34.767361+0 |
| `lines[].qc_by` | 8.8 | 8.8 | string:19 | Mulyadi · Budi Santoso |
| `lines[].qc_remark` | 8.0 | 7.1 | string:18 |  · ada cacat parah pada roll · noda KO |
| `lines[].qty_rolls` | 100.0 | 98.2 | number:153, null:2 | 1 |
| `lines[].quantity` | 100.0 | 100.0 | number:155 | 500 · 61.03 · 20 |
| `lines[].random_check_result` | 1.8 | 1.8 | string:4 | lulus · gagal |
| `lines[].remark` | 100.0 | 0.9 | string:155 | Inspeksi 4-point bersih (dem ·  |
| `lines[].repair_note` | 8.0 | 5.3 | string:18 |  · potong 30-45 |
| `lines[].return_item_index` | 51.3 | 51.3 | number:60 | 0 |
| `lines[].roll_id` | 100.0 | 98.2 | string:155 | roll_a9a6eb1e2e8b · roll_46e00bbe9585 · roll_cut_rsv_7aa5b6f2d75f |
| `lines[].roll_no` | 100.0 | 98.2 | string:155 | RL-46505 · RL-31983 · RL-31985-1 |
| `lines[].sku` | 100.0 | 98.2 | string:155 | DMO-YRN-WVN-30S · KNWVN0005-L-WGXX-XA-XX-XX · DMO-GRY-WVN-001 |
| `lines[].stdrt` | 8.0 | 5.3 | null:6, number:12 | 3.72 · 0 |
| `lines[].unit` | 100.0 | 100.0 | string:155 | kg · yard · meter |
| `lines[].width_actual` | 100.0 | 5.3 | null:149, number:6 | 147.32 |
| `lines[].width_standard` | 100.0 | 98.2 | number:153, null:2 | 0 · 1.47 · 1.5 |
| `lines[].yard_split` | 5.3 | 5.3 | object:6 |  |
| `md_only` | 99.1 | 99.1 | boolean:112 | false · true |
| `number` | 100.0 | 100.0 | string:113 | CST/INS-00001 · KSC/INS-00008 · KSC/INS-00009 |
| `quarantine_result` | 19.5 | 19.5 | object:22 |  |
| `quarantine_result.accepted_qty` | 19.5 | 19.5 | number:22 | 500 · 150 · 100 |
| `quarantine_result.at` | 19.5 | 19.5 | string:22 | 2026-10-22T04:17:19.106439+0 · 2026-10-22T18:53:30.392952+0 · 2026-10-22T18:53:31.521215+0 |
| `quarantine_result.by` | 19.5 | 19.5 | string:22 | Mulyadi · Budi Santoso |
| `quarantine_result.purchase_return` | 19.5 | 3.5 | null:18, object:4 |  |
| `quarantine_result.reject_disposition` | 19.5 | 7.1 | null:14, string:8 | return · damaged |
| `quarantine_result.rejected_qty` | 19.5 | 19.5 | number:22 | 0 · 50 · 100 |
| `quarantine_result.rejected_roll_ids` | 19.5 | 7.1 | array:22 |  |
| `quarantine_result.task_id` | 19.5 | 19.5 | string:22 | wms_bef96c0e9725 · wms_de7ca973f951 · wms_ca463945b75b |
| `quarantine_result.task_status` | 19.5 | 19.5 | string:22 | completed · qc_rejected |
| `ref_doc_id` | 100.0 | 84.1 | string:113 | po_5bfabb9a129a · sret_54a918a82410 · po_13e87908b394 |
| `ref_doc_number` | 100.0 | 84.1 | string:113 | CST/PO-00001 · SRET-00005 · KSC/PO-00010 |
| `ref_doc_type` | 100.0 | 84.1 | string:113 | purchase_order · sales_return · warehouse |
| `refs` | 82.3 | 33.6 | array:93 |  |
| `refs[].at` | 33.6 | 33.6 | string:40 | 2026-10-22T04:17:18.105167+0 · 2026-10-22T18:44:16.481538+0 · 2026-10-22T18:53:29.832142+0 |
| `refs[].doc_id` | 33.6 | 33.6 | string:40 | po_5bfabb9a129a · sret_54a918a82410 · po_13e87908b394 |
| `refs[].doc_number` | 33.6 | 33.6 | string:40 | CST/PO-00001 · SRET-00005 · KSC/PO-00010 |
| `refs[].doc_type` | 33.6 | 33.6 | string:40 | purchase_order · sales_return · md_sample |
| `refs[].note` | 33.6 | 33.6 | string:40 | inspeksi atas dokumen ini · acuan KSC/SMP-00018 · acuan KSC/SMP-00017 |
| `refs[].rel` | 33.6 | 33.6 | string:40 | parent · references |
| `reject_reason` | 100.0 | 3.5 | string:113 |  · Kain berlubang di banyak tit |
| `remark` | 100.0 | 81.4 | string:113 | Lolos inspeksi 4-point (demo ·  · Kain berlubang di banyak tit |
| `reopen_reason` | 100.0 | 0.0 | string:113 |  |
| `source_inspection_id` | 15.9 | 0.0 | string:18 |  |
| `source_task_id` | 15.9 | 0.0 | string:18 |  |
| `spk_date` | 100.0 | 100.0 | string:113 | 2026-10-22 · 2026-10-23 · 2026-10-24 |
| `started_at` | 100.0 | 32.7 | string:113 | 2026-10-22T04:17:18.765948+0 · 2026-10-22T18:45:49.416731+0 · 2026-10-22T18:53:29.954036+0 |
| `status` | 100.0 | 100.0 | string:113 | done · in_progress · assigned |
| `summary` | 100.0 | 100.0 | object:113 |  |
| `summary.color_mismatch` | 100.0 | 100.0 | number:113 | 0 · 1 |
| `summary.grade_after_counts` | 100.0 | 8.8 | object:113 |  |
| `summary.handfeel_mismatch` | 100.0 | 100.0 | number:113 | 0 |
| `summary.hold` | 100.0 | 100.0 | number:113 | 0 · 1 |
| `summary.inspected` | 100.0 | 100.0 | number:113 | 1 · 2 · 3 |
| `summary.lines` | 100.0 | 100.0 | number:113 | 1 · 2 · 3 |
| `summary.md_checked` | 50.4 | 50.4 | number:57 | 0 · 2 · 3 |
| `summary.measure` | 100.0 | 99.1 | number:112, null:1 | 500 · 81.03 · 150 |
| `summary.points_total` | 100.0 | 100.0 | number:113 | 0 · 8 · 20 |
| `summary.qc_checked` | 50.4 | 50.4 | number:57 | 1 · 0 · 2 |
| `summary.rejected` | 100.0 | 100.0 | number:113 | 0 · 1 |
| `summary.rolls` | 100.0 | 98.2 | number:111, null:2 | 1 · 2 · 3 |
| `summary.unit` | 100.0 | 99.1 | string:113 | kg · yard · meter |
| `supplier_id` | 100.0 | 31.0 | string:113 | sup_030091f8255b ·  · sup_a47057e2dfc2 |
| `supplier_name` | 100.0 | 31.0 | string:113 | PT Benang Sejahtera Abadi ·  · CV Grey Mandiri Majalaya |
| `task_id` | 100.0 | 31.0 | string:113 | wms_bef96c0e9725 ·  · wms_de7ca973f951 |
| `updated_at` | 100.0 | 100.0 | string:113 | 2026-10-22T04:17:19.106505+0 · 2026-10-22T18:50:28.933136+0 · 2026-10-22T18:53:30.393113+0 |

### `mdq_cuts` — 16 dokumen diprofil, 14 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `at` | 100.0 | 100.0 | string:16 | 2026-10-22T13:24:54.312110+0 · 2026-10-22T13:24:54.499427+0 · 2026-10-22T13:29:04.478550+0 |
| `basis` | 100.0 | 100.0 | string:16 | 0.25 yard |
| `by` | 100.0 | 100.0 | string:16 | Lestari Wulandari |
| `cut_yard` | 100.0 | 100.0 | number:16 | 0.25 |
| `id` | 100.0 | 100.0 | string:16 | mdqc_391492ce328e · mdqc_85aed5713d3d · mdqc_14723c6e8a14 |
| `inspection_id` | 100.0 | 100.0 | string:16 | ins_test_6630588f · ins_test_ea82f1f2 · ins_test_3860504b |
| `line_id` | 100.0 | 100.0 | string:16 | ln_0_3d0d8 · ln_1_fe469 · ln_0_8019a |
| `qty` | 100.0 | 100.0 | number:16 | 0.25 |
| `reason` | 100.0 | 100.0 | string:16 | Potong uji MD Quality |
| `roll_id` | 100.0 | 100.0 | string:16 | roll_3369fdaad8bd · roll_8408e44a6147 · roll_8fc6567625bc |
| `status` | 100.0 | 100.0 | string:16 | posted |
| `unit` | 100.0 | 100.0 | string:16 | yard |
| `value` | 100.0 | 100.0 | number:16 | 3240 · 3960 |
| `weight_kg` | 100.0 | 0.0 | null:16 |  |

### `material_reservations` — 56 dokumen diprofil, 25 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `basis` | 100.0 | 100.0 | string:56 | manual |
| `consumed_qty` | 42.9 | 42.9 | number:24 | 300 · 250 · 200 |
| `created_at` | 100.0 | 100.0 | string:56 | 2026-10-22T04:17:31.972362+0 · 2026-10-22T04:17:32.131581+0 · 2026-10-22T04:17:33.188287+0 |
| `created_by` | 100.0 | 100.0 | string:56 | Dewi Manager · Budi Santoso |
| `history` | 100.0 | 100.0 | array:56 |  |
| `history[].at` | 100.0 | 100.0 | string:115 | 2026-10-22T04:17:31.972373+0 · 2026-10-22T04:17:32.090320+0 · 2026-10-22T04:17:32.131591+0 |
| `history[].by` | 100.0 | 100.0 | string:91 | Dewi Manager · Budi Santoso |
| `history[].event` | 100.0 | 100.0 | string:115 | reserved · consumed · released |
| `history[].qty` | 100.0 | 100.0 | number:80 | 300 · 250 · 200 |
| `history[].reason` | 62.5 | 62.5 | string:35 | MKO selesai — sisa cadangan  · TEST_P05ACC batal · TEST_P05ACC |
| `history[].remaining` | 42.9 | 42.9 | number:24 | 0 · 40 |
| `id` | 100.0 | 100.0 | string:56 | mres_mko_4ae1fec91bc7 · mres_mko_bbd5de93daad · mres_mko_f28087d5e02b |
| `mko_id` | 100.0 | 100.0 | string:56 | mko_4ae1fec91bc7 · mko_bbd5de93daad · mko_f28087d5e02b |
| `mko_number` | 100.0 | 100.0 | string:56 | MKO-00001 · MKO-00002 · MKO-00003 |
| `output_product_id` | 100.0 | 100.0 | string:56 | prod_97ef39b63081 · prod_894c92cfbb1e · prod_7eaebe7db3cf |
| `owner_entity_id` | 100.0 | 100.0 | string:56 | ent_82b52ed6ee8b · ent_ksc · ent_kanda |
| `product_id` | 100.0 | 100.0 | string:56 | prod_cc00b3aed90e · prod_e234fb531063 · prod_894c92cfbb1e |
| `qty` | 100.0 | 100.0 | number:56 | 300 · 250 · 200 |
| `ref_id` | 100.0 | 100.0 | string:56 | mko_4ae1fec91bc7 · mko_bbd5de93daad · mko_f28087d5e02b |
| `ref_type` | 100.0 | 100.0 | string:56 | makloon_order |
| `release_reason` | 62.5 | 62.5 | string:35 | MKO selesai — sisa cadangan  · TEST_P05ACC batal · TEST_P05ACC |
| `required_qty` | 100.0 | 100.0 | number:56 | 300 · 250 · 200 |
| `shortage_qty` | 100.0 | 100.0 | number:56 | 0 · 5000 · 21.87 |
| `status` | 100.0 | 100.0 | string:56 | consumed · active · released |
| `updated_at` | 96.4 | 96.4 | string:54 | 2026-10-22T04:17:32.090257+0 · 2026-10-22T04:17:32.225038+0 · 2026-10-22T04:17:33.276912+0 |

### `warehouses` — 18 dokumen diprofil, 59 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `active` | 100.0 | 100.0 | boolean:18 | true · false |
| `address` | 16.7 | 11.1 | string:3 |  · Jl. Soekarno Hatta No. 100 · Jl. Mangga Dua Raya No. 22 |
| `city` | 100.0 | 94.4 | string:18 | Jakarta · Bandung · Surabaya |
| `city_code` | 33.3 | 33.3 | string:6 | 32.73 |
| `code` | 100.0 | 100.0 | string:18 | WH-JKT · WH-BDG · WH-SBY |
| `country` | 33.3 | 33.3 | string:6 | Indonesia |
| `country_code` | 33.3 | 33.3 | string:6 | ID |
| `created_at` | 100.0 | 100.0 | string:18 | 2026-10-22T04:11:14.727354+0 · 2026-10-22T04:11:14.727368+0 · 2026-10-22T04:11:14.727371+0 |
| `created_by` | 16.7 | 16.7 | string:3 | Import Stok Awal |
| `cutting_caps_at` | 5.6 | 5.6 | string:1 | 2026-10-24T02:04:30.154280+0 |
| `cutting_caps_by` | 5.6 | 5.6 | string:1 | Budi Santoso |
| `deactivated_reason` | 27.8 | 27.8 | string:5 | Diganti struktur gudang Ranc |
| `district` | 33.3 | 33.3 | string:6 | Bandung Wetan · Sukasari |
| `district_code` | 33.3 | 33.3 | string:6 | 32.73.09 · 32.73.01 |
| `entity_ids` | 88.9 | 61.1 | array:16 |  |
| `gate_config` | 38.9 | 38.9 | object:7 |  |
| `gate_config.physical_gate` | 38.9 | 38.9 | boolean:7 | false · true |
| `id` | 100.0 | 100.0 | string:18 | wh_jakarta · wh_bandung · wh_surabaya |
| `lat` | 66.7 | 16.7 | number:3, null:9 | -6.1751 · -6.9175 · -7.2504 |
| `lng` | 66.7 | 16.7 | number:3, null:9 | 106.865 · 107.6191 · 112.7688 |
| `location_status` | 33.3 | 33.3 | string:6 | verified |
| `name` | 100.0 | 100.0 | string:18 | Jakarta · Gudang Sukacita · Gudang Bandung Kopo · Gudang Surabaya Rungkut |
| `postal_code` | 33.3 | 33.3 | string:6 | 40115 · 40151 |
| `province` | 33.3 | 33.3 | string:6 | Jawa Barat |
| `province_code` | 33.3 | 33.3 | string:6 | 32 |
| `roles` | 38.9 | 38.9 | array:7 |  |
| `sharing_mode` | 88.9 | 88.9 | string:16 | dedicated · shared |
| `site_id` | 38.9 | 38.9 | string:7 | site_54bed6261604 · site_c0c8400b0017 · site_fd9f6aa41d36 |
| `storage_rules` | 38.9 | 38.9 | object:7 |  |
| `storage_rules.categories` | 38.9 | 0.0 | array:7 |  |
| `storage_rules.fabric_types` | 5.6 | 0.0 | array:1 |  |
| `storage_rules.grades` | 38.9 | 5.6 | array:7 |  |
| `storage_rules.mode` | 38.9 | 38.9 | string:7 | none · category · grade |
| `updated_at` | 83.3 | 83.3 | string:15 | 2026-10-22T04:17:55.459834+0 · 2026-10-22T04:17:48.980920+0 · 2026-10-22T04:17:48.985305+0 |
| `zones` | 100.0 | 100.0 | array:18 |  |
| `zones[].function` | 5.6 | 5.6 | string:1 | qc |
| `zones[].id` | 100.0 | 100.0 | string:43 | zone_jkt_a · zone_sim_wh_jkt_w · zone_sim_wh_jkt_k |
| `zones[].name` | 100.0 | 100.0 | string:43 | Zone A · Zona W · Woven/Printing (yar · Zona K · Knitting (kg) |
| `zones[].p02_demo` | 5.6 | 5.6 | boolean:1 | true |
| `zones[].racks` | 100.0 | 100.0 | array:43 |  |
| `zones[].sim_batch` | 66.7 | 66.7 | string:24 | SIMULASI_BIN_KN |

### `warehouse_sites` — 6 dokumen diprofil, 14 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `city` | 100.0 | 100.0 | string:6 | Bandung · Jakarta · Kota Surakarta |
| `city_code` | 50.0 | 50.0 | string:3 | 33.72 |
| `country` | 50.0 | 50.0 | string:3 | Indonesia |
| `country_code` | 50.0 | 50.0 | string:3 | ID |
| `created_at` | 100.0 | 100.0 | string:6 | 2026-10-22T04:16:30.225328+0 · 2026-10-22T04:16:30.235359+0 · 2026-10-22T04:16:30.236800+0 |
| `created_by` | 100.0 | 100.0 | string:6 | Demo Lengkap · Budi Santoso |
| `district` | 50.0 | 0.0 | string:3 |  |
| `district_code` | 50.0 | 0.0 | string:3 |  |
| `id` | 100.0 | 100.0 | string:6 | site_c0c8400b0017 · site_fd9f6aa41d36 · site_54bed6261604 |
| `location_status` | 50.0 | 50.0 | string:3 | verified |
| `name` | 100.0 | 100.0 | string:6 | Rancamalang · Soreang · Jakarta |
| `postal_code` | 50.0 | 50.0 | string:3 | 57111 |
| `province` | 50.0 | 50.0 | string:3 | Jawa Tengah |
| `province_code` | 50.0 | 50.0 | string:3 | 33 |

### `fact_stock_daily` — 2054 dokumen diprofil, 14 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `avail` | 100.0 | 100.0 | number:2054 | 599.51 · 449.44 · 3771.16 |
| `date` | 100.0 | 100.0 | string:2054 | 2026-10-22 · 2026-10-25 · 2026-10-26 |
| `dye_lot` | 100.0 | 100.0 | string:2054 | KANDA/LOT-2610-0031 · KANDA/LOT-2610-0033 · CST/LOT-2610-0113 |
| `fabric_type` | 100.0 | 100.0 | string:2054 | knit · woven |
| `grade` | 100.0 | 100.0 | string:2054 | A · B · C |
| `line_code` | 100.0 | 95.1 | string:2054 | knit · woven · printing |
| `owner_entity_id` | 100.0 | 100.0 | string:2054 | ent_kanda · ent_82b52ed6ee8b · ent_ksc |
| `product_id` | 100.0 | 100.0 | string:2054 | prod_b895e2f3702b · prod_afc76b2075d7 · prod_d920fd474483 |
| `qty` | 100.0 | 100.0 | number:2054 | 599.51 · 449.44 · 3771.16 |
| `reserved` | 100.0 | 100.0 | number:2054 | 0 · 500 · 1 |
| `rolls` | 100.0 | 100.0 | number:2054 | 24 · 18 · 63 |
| `unit` | 100.0 | 100.0 | string:2054 | kg · yard · meter |
| `value` | 100.0 | 100.0 | number:2054 | 18560829.6 · 13591065.6 · 48874233.6 |
| `warehouse_id` | 100.0 | 100.0 | string:2054 | wh_40e831c5bb53 · wh_adc8726d019e · wh_jakarta |

### `turn_marks` — 1115 dokumen diprofil, 4 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `collection` | 100.0 | 100.0 | string:1115 | purchase_orders · sales_orders · sales_returns |
| `created_at` | 100.0 | 100.0 | string:1115 | 2026-10-22T04:17:17.416062+0 · 2026-10-22T04:17:20.057633+0 · 2026-10-22T04:17:21.385173+0 |
| `doc_id` | 100.0 | 100.0 | string:1115 | po_5bfabb9a129a · po_59eb88c08c22 · po_4f65dcb9952a |
| `status` | 100.0 | 100.0 | string:1115 | pending · picked · partially_shipped |

### `roll_cost_history` — 22 dokumen diprofil, 18 path

| path | ada % | terisi % | tipe | contoh nilai |
|---|---:|---:|---|---|
| `actor` | 100.0 | 100.0 | string:22 | Budi Santoso · sistem (migrasi startup) |
| `at` | 100.0 | 100.0 | string:22 | 2026-10-22T07:17:56.968567+0 · 2026-10-22T07:17:56.992546+0 · 2026-10-22T07:17:57.007600+0 |
| `delta_unit_cost` | 100.0 | 100.0 | number:22 | -360 · -18000 · 9900 |
| `delta_value` | 100.0 | 100.0 | number:22 | -22204.8 · -22500 · -21816 |
| `direction` | 100.0 | 100.0 | string:22 | turun · naik |
| `entity_id` | 100.0 | 100.0 | string:22 | ent_ksc |
| `id` | 100.0 | 100.0 | string:22 | rch_2248f5c9bf3b · rch_508c4eced4f2 · rch_f109ba1d0c10 |
| `length_remaining` | 100.0 | 100.0 | number:22 | 61.68 · 62.5 · 60.6 |
| `new_unit_cost` | 100.0 | 100.0 | number:22 | 12600 · 0 · 9900 |
| `note` | 100.0 | 18.2 | string:22 |  · roll belum pernah dinilai —  |
| `old_unit_cost` | 100.0 | 100.0 | number:22 | 12960 · 18000 · 0 |
| `reason` | 100.0 | 100.0 | string:22 | interco_purchase_revalue · return_grade_impairment · startup_backfill |
| `reason_label` | 100.0 | 100.0 | string:22 | Dinilai ulang ke harga beli  · return_grade_impairment · Migrasi startup mengisi HPP  |
| `ref_id` | 100.0 | 81.8 | string:22 | icp_f41d6034cb48 · sret_TEST_U23_aabbfd_74e8 · sret_TEST_U23_af0d57_2708 |
| `ref_number` | 100.0 | 81.8 | string:22 | CST/IC-00001 · TEST_RET-U23-74e8 · TEST_RET-U23-2708 |
| `ref_type` | 100.0 | 81.8 | string:22 | interco · sales_return ·  |
| `roll_id` | 100.0 | 100.0 | string:22 | roll_74d7283673bd · roll_02fcc3dd0a34 · roll_19bb73be3e2d |
| `roll_no` | 100.0 | 100.0 | string:22 | RL-38018 · RL-38019 · RL-38020 |


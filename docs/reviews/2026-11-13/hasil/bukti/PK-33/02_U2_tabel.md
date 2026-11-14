| # | Endpoint (berkas · metode path) | Koleksi yang benar-benar ditulis | Atribusi salah pencacah lama | Dulu |
|---|---|---|---|---|
| 1 | `admin.py · POST /master-data/import-products` | products | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 2 | `ai_analytics.py · DELETE /my-templates/{template_id}` | ai_user_templates | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 3 | `ai_analytics.py · DELETE /schedules/{schedule_id}` | ai_schedules | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 4 | `ai_analytics.py · DELETE /sessions/{session_id}` | ai_chat_sessions | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 5 | `bank_reconciliation.py · DELETE /bank-reconciliation/formats/{format_id}` | bank_statement_formats | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 6 | `budgets.py · DELETE /finance/budgets/{budget_id}` | budgets | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 7 | `categories.py · DELETE /product-categories/{category_id}` | product_categories | `ocr_sample_service.delete`→ocr_samples | tercatat REVIEWED |
| 8 | `categories.py · POST /product-categories` | product_categories | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 9 | `color_library.py · DELETE /color-library/{color_id}` | color_library | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 10 | `consolidation.py · DELETE /finance/consolidation/eliminations/{elim_id}` | intercompany_eliminations | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 11 | `crm_omnichannel.py · DELETE /crm/interactions/{intx_id}` | crm_interactions | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 12 | `crm_omnichannel.py · DELETE /crm/leads/{lead_id}` | crm_leads | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 13 | `customer_prices.py · DELETE /customer-prices/{price_id}` | — | `ocr_sample_service.delete`→ocr_samples; `pricelist_service.deactivate_price`→entity_prices | belum ditinjau |
| 14 | `customers.py · PATCH /customers/{customer_id}` | customers | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 15 | `customers.py · POST /customers/{customer_id}/addresses` | customers | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 16 | `cycle_count.py · POST /cycle-count/sessions/{session_id}/approve` | cycle_count_sessions | `design_ownership_service.claim`→design_gallery; `dispatch_payment_gate.release`→sales_orders | tercatat REVIEWED |
| 17 | `design_gallery.py · DELETE /design-gallery/{gallery_id}` | design_gallery | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 18 | `design_gallery.py · DELETE /design-gallery/{gallery_id}/files/{file_id}/comments/{comment_id}` | design_gallery | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 19 | `design_gallery.py · DELETE /design-gallery/{gallery_id}/rating` | design_gallery | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 20 | `design_studio.py · DELETE /design-gallery/{gallery_id}/colorways/{cw_id}` | design_gallery | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 21 | `documents.py · DELETE /document-templates/{template_id}` | document_templates | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 22 | `entities.py · DELETE /entities/{entity_id}/tax-status/pending` | business_entities | `ocr_sample_service.delete`→ocr_samples | tercatat REVIEWED |
| 23 | `entity_masters.py · DELETE /entity-masters/{kind}/{row_id}` | — | `ocr_sample_service.delete`→ocr_samples; `data_hygiene_service.revert`→data_hygiene_log; `ai_actions._segarkan`→ai_action_proposals | belum ditinjau |
| 24 | `entity_masters.py · POST /entity-masters/{kind}` | — | `handheld_devices.create`→rfid_devices; `ai_actions._segarkan`→ai_action_proposals | belum ditinjau |
| 25 | `export_center.py · DELETE /templates/{tpl_id}` | export_templates | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 26 | `gl.py · DELETE /gl/accounts/{code}` | gl_accounts | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 27 | `handheld.py · POST /tasks/{kind}/{doc_id}/complete` | — | `cycle_count_service.complete`→rfid_cycle_counts, rfid_verify_sessions | belum ditinjau |
| 28 | `hr.py · DELETE /hr/employees/{employee_id}` | hr_employees | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 29 | `hr.py · DELETE /hr/org-units/{unit_id}` | hr_org_units | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 30 | `hr.py · PATCH /hr/employees/{employee_id}` | hr_employees | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 31 | `hr_attendance.py · DELETE /hr/devices/{dev_id}` | hr_devices | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 32 | `hr_attendance.py · DELETE /hr/geofences/{geo_id}` | hr_geofences | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 33 | `hr_attendance.py · DELETE /hr/shifts/{shift_id}` | hr_shifts | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 34 | `hr_kpi.py · DELETE /hr/kpi/{kpi_id}` | hr_kpi | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 35 | `incentive_rates.py · DELETE /incentive-rates/{rate_id}` | incentive_rates | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 36 | `incentive_rates.py · POST /incentive-rates` | incentive_rates | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 37 | `inventory.py · POST /inventory/rolls/{roll_id}/reservations/{reservation_id}/cut` | inventory_rolls | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 38 | `makloons.py · DELETE /makloons/{makloon_id}` | makloons | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 39 | `marketing.py · DELETE /marketing/posts/{pid}` | mkt_posts | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 40 | `marketing.py · DELETE /marketing/posts/{pid}/attachments/{fid}` | mkt_posts | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 41 | `marketing.py · DELETE /marketing/templates/{tid}` | mkt_templates | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 42 | `outbound_picking.py · POST /outbound/loading-check/{session_id}/complete` | rfid_verify_sessions | `cycle_count_service.complete`→rfid_cycle_counts, rfid_verify_sessions | tercatat REVIEWED |
| 43 | `pdf.py · DELETE /templates/{doc_type}` | pdf_templates | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 44 | `pegging.py · DELETE /inventory/rolls/{roll_id}/earmark` | inventory_rolls | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 45 | `price_approvals.py · DELETE /price-approvals/{approval_id}` | price_approvals | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 46 | `price_approvals.py · DELETE /price-approvals/{approval_id}/attachments/{att_id}` | price_approvals | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 47 | `pricelist.py · DELETE /pricelist/override/{product_id}` | entity_prices | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 48 | `pricelist.py · DELETE /pricelist/{price_id}` | entity_prices | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 49 | `process_recipes.py · DELETE /process-recipes/{recipe_id}` | process_recipes | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 50 | `product_templates.py · DELETE /product-templates/{template_id}` | product_templates | `ocr_sample_service.delete`→ocr_samples | tercatat REVIEWED |
| 51 | `production.py · DELETE /production/boms/{bom_id}` | mfg_boms | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 52 | `products.py · DELETE /products/{product_id}` | products | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 53 | `products.py · PATCH /products/{product_id}` | products | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 54 | `products.py · POST /products` | products | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 55 | `purchase_requisitions.py · POST /purchase-requisitions/{pr_id}/approve` | purchase_requisitions | `return_grade_impairment.record`→inventory_rolls, sales_returns | belum ditinjau |
| 56 | `purchase_requisitions.py · POST /purchase-requisitions/{pr_id}/reject` | purchase_requisitions | `return_grade_impairment.record`→inventory_rolls, sales_returns | belum ditinjau |
| 57 | `purchase_returns.py · DELETE /purchase-returns/{return_id}` | purchase_returns | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 58 | `return_policies.py · DELETE /sales-return-policies/{policy_id}` | sales_return_policies | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 59 | `rfid.py · DELETE /rfid/devices/{device_id}` | rfid_devices | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 60 | `rfq.py · POST /rfqs/{rfq_id}/quote` | rfqs | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 61 | `rnd.py · POST /rnd/specs/{spec_id}/approve` | products | `return_grade_impairment.record`→inventory_rolls, sales_returns | belum ditinjau |
| 62 | `rnd.py · POST /rnd/specs/{spec_id}/reject` | — | `return_grade_impairment.record`→inventory_rolls, sales_returns | belum ditinjau |
| 63 | `sales_return_exceptions.py · DELETE /sales-returns/{return_id}/compensation` | sales_returns | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 64 | `sales_returns.py · DELETE /sales-returns/{return_id}/attachments/{att_id}` | sales_returns | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 65 | `sales_returns.py · POST /sales-returns/{return_id}/roll-settlement/{settlement_id}/complete` | — | `cycle_count_service.complete`→rfid_cycle_counts, rfid_verify_sessions | belum ditinjau |
| 66 | `sample_orders.py · POST /sample-orders/{order_id}/approve-payment` | sales_orders | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 67 | `scheduler.py · PUT /scheduler/settings` | system_settings | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 68 | `settings.py · DELETE /payment-terms/{term_id}` | payment_terms | `ocr_sample_service.delete`→ocr_samples; `data_hygiene_service.revert`→data_hygiene_log | tercatat REVIEWED |
| 69 | `so_approvals.py · POST /sales-orders/{order_id}/approvals/{approval_id}/decide` | — | `design_ownership_service.claim`→design_gallery; `dispatch_payment_gate.release`→sales_orders | tercatat REVIEWED |
| 70 | `special_orders.py · DELETE /special-orders/{order_id}` | special_orders | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 71 | `special_orders.py · POST /special-orders/{order_id}/convert-to-so` | special_orders | `design_ownership_service.claim`→design_gallery; `dispatch_payment_gate.release`→sales_orders | tercatat REVIEWED |
| 72 | `special_orders.py · POST /special-orders/{order_id}/reject` | special_orders | `return_grade_impairment.record`→inventory_rolls, sales_returns | belum ditinjau |
| 73 | `suppliers.py · DELETE /supplier-price-list/{entry_id}` | supplier_price_lists | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 74 | `suppliers.py · DELETE /suppliers/{supplier_id}` | suppliers | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 75 | `suppliers.py · PATCH /suppliers/{supplier_id}` | suppliers | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 76 | `tax_center.py · DELETE /tax/pph-records/{record_id}` | tax_pph_records | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 77 | `uoms.py · DELETE /uoms/{uom_id}` | uoms | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 78 | `users.py · DELETE /users/{user_id}` | users | `ocr_sample_service.delete`→ocr_samples | tercatat REVIEWED |
| 79 | `vendor_bills.py · POST /vendor-bills` | purchase_orders | `design_ownership_service.claim`→design_gallery; `dispatch_payment_gate.release`→sales_orders | belum ditinjau |
| 80 | `warehouse_sites.py · DELETE /warehouse-sites/{site_id}` | warehouse_sites | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |
| 81 | `warehouse_sites.py · PATCH /warehouse-sites/{site_id}` | warehouse_sites | `ocr_sample_service.update`→ocr_samples | belum ditinjau |
| 82 | `warehouses.py · DELETE /warehouses/{warehouse_id}` | warehouses | `ocr_sample_service.delete`→ocr_samples | belum ditinjau |

| # | Endpoint baru masuk | Koleksi | Lewat layanan (impor nyata) |
|---|---|---|---|
| 1 | `cutting.py · POST /tasks/{task_id}/receive` | sales_orders, wms_tasks | `cutting_service.receive` |
| 2 | `data_hygiene.py · POST /data-hygiene/run` | data_hygiene_log, data_hygiene_runs | `data_hygiene_service.run` |
| 3 | `inspections.py · POST /inspections/{ins_id}/lines/{line_id}/mdq-cut` | inspections, inventory_movements, inventory_rolls, mdq_cuts | `mdq_cut_service.cut` |
| 4 | `marketing.py · PATCH /marketing/accounts/{aid}` | mkt_accounts, mkt_posts | `marketing_ext.update_account` |
| 5 | `purchase_orders.py · POST /purchase-orders/{po_id}/amend` | po_variance_tasks, purchase_orders, wms_tasks | `po_amendment_service.amend_po`; `po_variance_task_service.close_amendment_tasks` |
| 6 | `transfers.py · POST /transfers/{transfer_id}/exceptions/{exc_id}/resolve` | inventory_movements, inventory_rolls | `transfer_receipt_service.resolve` |

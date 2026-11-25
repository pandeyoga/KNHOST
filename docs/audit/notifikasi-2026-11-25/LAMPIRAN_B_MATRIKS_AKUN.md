# Matriks akun × jenis notifikasi yang terlihat di lonceng (data demo, 2026-11-25)

Sumber: `GET /api/notifications` dan `GET /api/notifications/unread-count` per akun, lewat login API (`probe.py`).
Sel = total/belum-dibaca. Baris 'bawaan' = header `X-Entity-Id` = PT rumah dan `?entity_id=` PT rumah (persis
`useAppActions.loadNotifications` sesudah login). Baris 'gabungan' = `X-Entity-Id: all` dan `entity_id=all`.
Kolom 'lencana' = angka `unread-count` pada mode itu.

| akun | peran | mode | lencana | amendment_approval | backorder_ready | finance_case | inspection_assigned | interco_receipt_auto_fulfilled | low_stock | order_approval | penalty_draft | po_approval | restock_request | turn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| admin | admin | bawaan ent_ksc | 21 | 4/2 | · | 3/3 | · | · | 9/9 | 1/1 | 1/1 | 2/2 | 3/3 | · |
| admin | admin | gabungan | 26 | 4/2 | 1/1 | 3/3 | · | 1/1 | 9/9 | 1/1 | 3/3 | 3/3 | 3/3 | · |
| sales | sales | bawaan ent_ksc | 0 | · | · | · | · | · | · | · | · | · | · | 1/0 |
| sales | sales | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | 1/0 |
| sales2 | sales | bawaan ent_ksc | 0 | · | · | · | · | · | · | · | · | · | · | · |
| sales2 | sales | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | · |
| sales3 | sales | bawaan ent_kanda | 0 | · | · | · | · | · | · | · | · | · | · | · |
| sales3 | sales | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | · |
| manager | manager | bawaan ent_ksc | 23 | 4/2 | · | 3/3 | · | · | 9/9 | 1/1 | 1/1 | 2/2 | 3/3 | 3/2 |
| manager | manager | gabungan | 26 | 4/2 | 1/1 | 3/3 | · | · | 9/9 | 1/1 | 3/3 | 2/2 | 3/3 | 3/2 |
| manager.printing | manager | bawaan ent_ksc | 23 | 4/2 | · | 3/3 | · | · | 9/9 | 1/1 | 1/1 | 2/2 | 3/3 | 3/2 |
| manager.printing | manager | gabungan | 26 | 4/2 | 1/1 | 3/3 | · | · | 9/9 | 1/1 | 3/3 | 2/2 | 3/3 | 3/2 |
| adminsales.lama | manager | bawaan ent_ksc | 23 | 4/2 | · | 3/3 | · | · | 9/9 | 1/1 | 1/1 | 2/2 | 3/3 | 3/2 |
| adminsales.lama | manager | gabungan | 26 | 4/2 | 1/1 | 3/3 | · | · | 9/9 | 1/1 | 3/3 | 2/2 | 3/3 | 3/2 |
| warehouse | warehouse | bawaan ent_ksc | 11 | · | · | · | 1/1 | · | · | · | · | · | · | 10/10 |
| warehouse | warehouse | gabungan | 11 | · | · | · | 1/1 | · | · | · | · | · | · | 10/10 |
| warehouse2 | warehouse | bawaan ent_ksc | 10 | · | · | · | · | · | · | · | · | · | · | 10/10 |
| warehouse2 | warehouse | gabungan | 10 | · | · | · | · | · | · | · | · | · | · | 10/10 |
| salesadmin | sales_admin | bawaan ent_ksc | 1 | · | · | · | · | · | · | · | · | · | · | 2/1 |
| salesadmin | sales_admin | gabungan | 2 | · | · | · | · | 1/1 | · | · | · | · | · | 2/1 |
| finance | finance | bawaan ent_ksc | 13 | · | · | · | · | · | 9/9 | 1/1 | · | · | · | 3/3 |
| finance | finance | gabungan | 13 | · | · | · | · | · | 9/9 | 1/1 | · | · | · | 3/3 |
| dewi.printing | sales | bawaan ent_ksc | 0 | · | · | · | · | · | · | · | · | · | · | · |
| dewi.printing | sales | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | · |
| designer | designer | bawaan ent_ksc | 0 | · | · | · | · | · | · | · | · | · | · | · |
| designer | designer | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | · |
| driver | driver | bawaan ent_ksc | 0 | · | · | · | · | · | · | · | · | · | · | · |
| driver | driver | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | · |
| md | md | bawaan ent_ksc | 0 | · | · | · | · | · | · | · | · | · | · | · |
| md | md | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | · |
| wh.admin | warehouse_admin | bawaan ent_ksc | 0 | · | · | · | · | · | · | · | · | · | · | · |
| wh.admin | warehouse_admin | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | · |
| sampleadmin | sample_admin | bawaan ent_ksc | 0 | · | · | · | · | · | · | · | · | · | · | · |
| sampleadmin | sample_admin | gabungan | 0 | · | · | · | · | · | · | · | · | · | · | · |

## Rincian per akun (mode gabungan): id · jenis · PT · alamat · tautan · keparahan · dibaca · aksi

### admin (admin, PT terbaca ['ent_ksc', 'ent_kanda', 'ent_dc3bb8e9ba94']) — 28 notifikasi
- ntf_5662b268370b · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_323e7957f240 · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_02c37345848d · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_2ca06be86a51 · interco_receipt_auto_fulfilled · ent_kanda · role=sales_admin · link=pending-so · sev=info · read=False · aksi=-
- ntf_d8958c281395 · backorder_ready · ent_kanda · role=manager · link=orders · sev=info · read=False · aksi=-
- ntf_ed9081f7f442 · penalty_draft · ent_ksc · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_c0f6c1b5fddd · penalty_draft · ent_kanda · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_9c921eab57a7 · penalty_draft · ent_kanda · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_defc69c30e3b · po_approval · ent_ksc · role=manager · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_960c57708c51 · po_approval · ent_kanda · role=admin · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_3795dfd51140 · po_approval · ent_ksc · role=manager · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_85d09bb28f32 · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_0ce498e7156c · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_701d4ef4a898 · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_280e790a6995 · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=True · aksi=amendment
- ntf_d46d39dff40a · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=True · aksi=amendment
- ntf_cdcce441ebc2 · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=False · aksi=amendment
- ntf_460957b159fb · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=False · aksi=amendment
- ntf_9b1695f24721 · order_approval · ent_ksc · user=user_admin_01 · link=orders · sev=info · read=False · aksi=-
- ntf_9be08c750f63 · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_bceb66ae0b64 · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_f3df047dec99 · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_6c08722e5393 · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_aa09641d9a0e · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_aba74d784dcf · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_43ce9febbff8 · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_6e40c9bc0bbf · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_7727fd98eddf · low_stock · ent_ksc · user=user_admin_01 · link=reorder · sev=warning · read=False · aksi=-

### sales (sales, PT terbaca ['ent_ksc']) — 1 notifikasi
- ntf_f01d5abbdef2 · turn · ent_ksc · user=user_sales_01 · link=orders · sev=info · read=True · aksi=turn
- Uji PT tak ditugaskan: ent_kanda → HTTP 403, ent_dc3bb8e9ba94 → HTTP 403

### sales2 (sales, PT terbaca ['ent_ksc']) — 0 notifikasi
- Uji PT tak ditugaskan: ent_kanda → HTTP 403, ent_dc3bb8e9ba94 → HTTP 403

### sales3 (sales, PT terbaca ['ent_kanda']) — 0 notifikasi
- Uji PT tak ditugaskan: ent_ksc → HTTP 403, ent_dc3bb8e9ba94 → HTTP 403

### manager (manager, PT terbaca ['ent_ksc', 'ent_kanda', 'ent_dc3bb8e9ba94']) — 29 notifikasi
- ntf_6ae45c8ccd75 · turn · ent_ksc · user=user_manager_01 · link=approvals · sev=info · read=False · aksi=turn
- ntf_7f44210c33d7 · turn · ent_ksc · user=user_manager_01 · link=approvals · sev=info · read=False · aksi=turn
- ntf_5662b268370b · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_323e7957f240 · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_02c37345848d · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_d8958c281395 · backorder_ready · ent_kanda · role=manager · link=orders · sev=info · read=False · aksi=-
- ntf_ed9081f7f442 · penalty_draft · ent_ksc · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_c0f6c1b5fddd · penalty_draft · ent_kanda · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_9c921eab57a7 · penalty_draft · ent_kanda · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_defc69c30e3b · po_approval · ent_ksc · role=manager · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_3795dfd51140 · po_approval · ent_ksc · role=manager · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_fa4cf5c49df8 · turn · ent_ksc · user=user_manager_01 · link=approvals · sev=info · read=True · aksi=turn
- ntf_85d09bb28f32 · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_0ce498e7156c · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_701d4ef4a898 · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_280e790a6995 · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=True · aksi=amendment
- ntf_d46d39dff40a · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=True · aksi=amendment
- ntf_cdcce441ebc2 · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=False · aksi=amendment
- ntf_460957b159fb · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=False · aksi=amendment
- ntf_2f91a2c7d4fd · order_approval · ent_ksc · user=user_manager_01 · link=orders · sev=info · read=False · aksi=-
- ntf_d5728467eae1 · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_5e0d44154e25 · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_6921ca286656 · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_ad43f429c897 · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_6538b10d5035 · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_180952f5a8c6 · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_0ebf2d047a7c · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_c1c338e33748 · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_d331aa10e402 · low_stock · ent_ksc · user=user_manager_01 · link=reorder · sev=warning · read=False · aksi=-

### manager.printing (manager, PT terbaca ['ent_ksc', 'ent_kanda', 'ent_dc3bb8e9ba94']) — 29 notifikasi
- ntf_c30524356b03 · turn · ent_ksc · user=user_manager_03 · link=approvals · sev=info · read=False · aksi=turn
- ntf_cc88fbabc230 · turn · ent_ksc · user=user_manager_03 · link=approvals · sev=info · read=False · aksi=turn
- ntf_5662b268370b · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_323e7957f240 · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_02c37345848d · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_d8958c281395 · backorder_ready · ent_kanda · role=manager · link=orders · sev=info · read=False · aksi=-
- ntf_ed9081f7f442 · penalty_draft · ent_ksc · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_c0f6c1b5fddd · penalty_draft · ent_kanda · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_9c921eab57a7 · penalty_draft · ent_kanda · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_defc69c30e3b · po_approval · ent_ksc · role=manager · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_3795dfd51140 · po_approval · ent_ksc · role=manager · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_c2a1fb77f7eb · turn · ent_ksc · user=user_manager_03 · link=approvals · sev=info · read=True · aksi=turn
- ntf_85d09bb28f32 · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_0ce498e7156c · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_701d4ef4a898 · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_280e790a6995 · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=True · aksi=amendment
- ntf_d46d39dff40a · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=True · aksi=amendment
- ntf_cdcce441ebc2 · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=False · aksi=amendment
- ntf_460957b159fb · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=False · aksi=amendment
- ntf_79a896866678 · order_approval · ent_ksc · user=user_manager_03 · link=orders · sev=info · read=False · aksi=-
- ntf_8adf27077595 · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-
- ntf_7a6026509fee · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-
- ntf_b1d178b173f6 · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-
- ntf_0635f484022a · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-
- ntf_2ce8c4ec217a · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-
- ntf_88e86c09032c · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-
- ntf_ed8f9f9374c8 · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-
- ntf_40ad13d5ac59 · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-
- ntf_a5d0ba9e6263 · low_stock · ent_ksc · user=user_manager_03 · link=reorder · sev=warning · read=False · aksi=-

### adminsales.lama (manager, PT terbaca ['ent_ksc', 'ent_kanda', 'ent_dc3bb8e9ba94']) — 29 notifikasi
- ntf_6dff17b4e67b · turn · ent_ksc · user=user_manager_02 · link=approvals · sev=info · read=False · aksi=turn
- ntf_0a1a8c41e778 · turn · ent_ksc · user=user_manager_02 · link=approvals · sev=info · read=False · aksi=turn
- ntf_5662b268370b · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_323e7957f240 · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_02c37345848d · finance_case · ent_ksc · role=manager · link=finance-cases · sev=warning · read=False · aksi=finance_case
- ntf_d8958c281395 · backorder_ready · ent_kanda · role=manager · link=orders · sev=info · read=False · aksi=-
- ntf_ed9081f7f442 · penalty_draft · ent_ksc · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_c0f6c1b5fddd · penalty_draft · ent_kanda · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_9c921eab57a7 · penalty_draft · ent_kanda · role=manager · link=payment-plans · sev=warning · read=False · aksi=-
- ntf_defc69c30e3b · po_approval · ent_ksc · role=manager · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_3795dfd51140 · po_approval · ent_ksc · role=manager · link=purchase-approval · sev=info · read=False · aksi=po_approve
- ntf_f8441851817d · turn · ent_ksc · user=user_manager_02 · link=approvals · sev=info · read=True · aksi=turn
- ntf_85d09bb28f32 · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_0ce498e7156c · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_701d4ef4a898 · restock_request · ent_ksc · role=manager · link=purchase-requisitions · sev=warning · read=False · aksi=-
- ntf_280e790a6995 · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=True · aksi=amendment
- ntf_d46d39dff40a · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=True · aksi=amendment
- ntf_cdcce441ebc2 · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=False · aksi=amendment
- ntf_460957b159fb · amendment_approval · ent_ksc · role=manager · link=amendments · sev=warning · read=False · aksi=amendment
- ntf_4a68e2ad9460 · order_approval · ent_ksc · user=user_manager_02 · link=orders · sev=info · read=False · aksi=-
- ntf_534d953ba0ba · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-
- ntf_965b066eb70e · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-
- ntf_a290c6a8c896 · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-
- ntf_a21089dc7b2b · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-
- ntf_94dab932e7e1 · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-
- ntf_ff4c77aabcbd · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-
- ntf_a822d44d1d56 · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-
- ntf_266e222f2010 · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-
- ntf_5e36b2930027 · low_stock · ent_ksc · user=user_manager_02 · link=reorder · sev=warning · read=False · aksi=-

### warehouse (warehouse, PT terbaca ['ent_ksc']) — 11 notifikasi
- ntf_e50cd03859dd · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_dc85c9dc5c49 · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_b34de1470829 · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_0ad20c28501a · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_204559e43396 · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_9baf7f832a33 · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_f509859d36a1 · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_c524290668bf · turn · ent_ksc · user=user_wh_01 · link=orders · sev=info · read=False · aksi=turn
- ntf_ac6987ee9af8 · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_8d2969c5fd19 · turn · ent_ksc · user=user_wh_01 · link=operations · sev=info · read=False · aksi=turn
- ntf_cc3e23563c5f · inspection_assigned · ent_ksc · user=user_wh_01 · link=inspections · sev=info · read=False · aksi=-
- Uji PT tak ditugaskan: ent_kanda → HTTP 403, ent_dc3bb8e9ba94 → HTTP 403

### warehouse2 (warehouse, PT terbaca ['ent_ksc']) — 10 notifikasi
- ntf_46f295a45977 · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- ntf_9e7e835a5b22 · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- ntf_bd46a909faf0 · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- ntf_14b0ec5d5c48 · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- ntf_e2d40dc6d35a · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- ntf_703d9767252e · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- ntf_de34fad0762f · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- ntf_f607ffaa2f48 · turn · ent_ksc · user=user_wh_02 · link=orders · sev=info · read=False · aksi=turn
- ntf_bddf947d5c53 · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- ntf_ad1cd0ddb456 · turn · ent_ksc · user=user_wh_02 · link=operations · sev=info · read=False · aksi=turn
- Uji PT tak ditugaskan: ent_kanda → HTTP 403, ent_dc3bb8e9ba94 → HTTP 403

### salesadmin (sales_admin, PT terbaca ['ent_ksc', 'ent_kanda']) — 3 notifikasi
- ntf_5386093bd528 · turn · ent_ksc · user=user_sales_admin_01 · link=orders · sev=info · read=False · aksi=turn
- ntf_2ca06be86a51 · interco_receipt_auto_fulfilled · ent_kanda · role=sales_admin · link=pending-so · sev=info · read=False · aksi=-
- ntf_b6352a48734d · turn · ent_ksc · user=user_sales_admin_01 · link=orders · sev=info · read=True · aksi=turn
- Uji PT tak ditugaskan: ent_dc3bb8e9ba94 → HTTP 403

### finance (finance, PT terbaca ['ent_ksc', 'ent_kanda', 'ent_dc3bb8e9ba94']) — 13 notifikasi
- ntf_4497c9a8a666 · turn · ent_ksc · user=user_finance_01 · link=finance · sev=info · read=False · aksi=turn
- ntf_a8d9777ebdf3 · turn · ent_ksc · user=user_finance_01 · link=finance · sev=info · read=False · aksi=turn
- ntf_70656974b98d · turn · ent_ksc · user=user_finance_01 · link=finance · sev=info · read=False · aksi=turn
- ntf_a7d514aadc3e · order_approval · ent_ksc · user=user_finance_01 · link=orders · sev=info · read=False · aksi=-
- ntf_ff8cbc078ce4 · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_5bb8e245e9d5 · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_378017b1bef7 · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_6e6460a2fcf9 · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_40404d29dd39 · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_b2c4d0de1219 · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_6984b317bf41 · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_01e5d4991a72 · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-
- ntf_a258e220e4dc · low_stock · ent_ksc · user=user_finance_01 · link=reorder · sev=warning · read=False · aksi=-

### dewi.printing (sales, PT terbaca ['ent_ksc']) — 0 notifikasi
- Uji PT tak ditugaskan: ent_kanda → HTTP 403, ent_dc3bb8e9ba94 → HTTP 403

### designer (designer, PT terbaca ['ent_ksc']) — 0 notifikasi
- Uji PT tak ditugaskan: ent_kanda → HTTP 403, ent_dc3bb8e9ba94 → HTTP 403

### driver (driver, PT terbaca ['ent_ksc']) — 0 notifikasi
- Uji PT tak ditugaskan: ent_kanda → HTTP 403, ent_dc3bb8e9ba94 → HTTP 403

### md (md, PT terbaca ['ent_ksc', 'ent_kanda']) — 0 notifikasi
- Uji PT tak ditugaskan: ent_dc3bb8e9ba94 → HTTP 403

### wh.admin (warehouse_admin, PT terbaca ['ent_ksc', 'ent_kanda']) — 0 notifikasi
- Uji PT tak ditugaskan: ent_dc3bb8e9ba94 → HTTP 403

### sampleadmin (sample_admin, PT terbaca ['ent_ksc', 'ent_kanda']) — 0 notifikasi
- Uji PT tak ditugaskan: ent_dc3bb8e9ba94 → HTTP 403


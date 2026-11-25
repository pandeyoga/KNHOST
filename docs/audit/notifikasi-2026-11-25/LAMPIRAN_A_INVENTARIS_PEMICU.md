# Inventaris pemicu notifikasi backend — KNHOST @ 1ecbbed (25 Nov 2026)

Sumber: pembacaan kode `backend/services/*`, `backend/routers/*`; matriks izin DB demo (`permission_settings.matrix`,
identik dengan `DEFAULT_PERMISSIONS`); 105 dokumen `notifications` di MongoDB demo; daftar layar
`frontend/src/AppViewRouter.jsx` + `config/viewAliases.js`. Tidak ada berkas repo / DB yang diubah.

## Legenda
* **Alamat**: `IZIN(r.a)` = `create_addressed(permission=…)` satu dokumen per orang pemegang izin (pagar PT);
  `PERAN[x,y]→orang` = `create_addressed(roles=…)` per orang; `PERAN(x)` = satu dokumen `recipient_role=x` (siaran ke
  seluruh pemegang peran + peran kustom ber-`notify_like` x); `KEBIJAKAN(r)` = `reminder_policy.notify` (bawaan di kurung);
  `ORANG` = `recipient_user` saja.
* **PT**: `isi` = `entity_id` dokumen; `KOSONG` = None/"" (lolos ke semua PT).
* **Dedupe**: `U` unread (bawaan), `H` day, `E` ever, `–` dedupe=False / tanpa ref.
* **Link**: `✓` id layar dirender; `✓a` alias frontend; `✗` tidak dirender di desktop (layar kosong); `⚠R` tersembunyi oleh
  saringan relevansi (`notification_scope.relevance_filter`) bagi penerima peran (hanya admin melihat).
* **Tutup**: `res` = `resolve_action`/penandaan dibaca saat keputusan; `–` bukan notifikasi aksi; `TIDAK` = notifikasi
  "menunggu keputusan" tetap menyala setelah diputus.
* Penanda: **[V]** terverifikasi kode/data, **[D]** dugaan.

## Tabel

| # | Jenis | Pemicu (berkas:baris — peristiwa) | Alamat | Izin seharusnya (layar/aksi) | PT | Dedupe | Sev | Link | Tutup | Temuan |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | low_stock | notification_service.py:203 — job pindai: stok tersedia < reorder_point | IZIN(purchase_order.create) + divisi opsional | purchase_requisition.create (MD/Admin Gudang yang memesan ulang) | isi | H/orang | warning | reorder ✓ | – | Demo: 45 dok = 9 produk × admin, finance, 3 manajer; MD & Admin Gudang tidak menerima [V] |
| 2 | reservation_expiring | notification_service.py:238-247 — job: booking stok SO ≤ N jam lagi habis | IZIN(order.confirm) + sales_id; + IZIN(order.approve) bila menunggu manajer | order.confirm / order.approve | isi | U/orang | warning | orders ✓ | – | Penerima ikut sample_admin & finance; salinan sales kosong bila `sales_id` kosong (0/10 SO demo) [V] |
| 3 | order_approval | notification_service.py:254 — job: SO berstatus waiting_approval | IZIN(order.approve) | order.approve | isi | U/orang | info | orders ✓ | TIDAK (tanpa action_type) | Ganda dengan `turn` (Setujui pesanan) untuk SO yang sama, audiens beda (finance dapat ini, tidak dapat turn) [V] |
| 4 | order_split | notification_service.py:270 — job: SO split gudang aktif | IZIN(wms.dispatch) | wms.dispatch | isi | U/orang | info | operations ✓ | – | Finance ikut menerima (pemegang wms.dispatch) [V] |
| 5 | po_approval | notification_service.py:166 (`notify_po_awaiting_approval`; dipanggil routers/purchase_orders.py:813,840,977, pr_sourcing_service.py:737, rfq_service.py:280, job) — PO masuk waiting_approval | PERAN(required_approval_role, bawaan manager) | purchase_order.approve | isi | U | info/warning | purchase-approval ✓ | res (purchase_orders.py:974,1006,1061) | Finance pemegang purchase_order.approve tidak menerima [V] |
| 6 | po_stage_stuck | notification_service.py:434 — job: tahap PO in_progress > N hari | IZIN(purchase_order.create) | purchase_order.update | isi | H/orang | warning | purchase-orders ✓a | – | – |
| 7 | special_order_approval | notification_service.py:351 (endpoint special_orders.py:362,528 + job) — PO custom menunggu ACC | IZIN(order.approve) + PERAN required_approval_role →orang | order.approve / aturan persetujuan | isi | E/orang | warning | special-orders ✓ | TIDAK (approve/reject special_orders.py:1054,1146 tak menutup & tak memberi tahu pengaju) | – |
| 8 | cycle_count_reservation_hit | notification_service.py:472 (stock_count_service.py:146) — opname susut memotong roll ber-reservasi | ORANG sales pemilik; cadangan PERAN(sales_admin) | order.update | isi | U | warning | orders ✓ | – (order_open) | – |
| 9 | ar_overdue | alert_service.py:81 — job: pelanggan berpiutang lewat tempo | KEBIJAKAN(manager) | ar_receipt.create / penagihan (finance) | **KOSONG** (lintas PT) | H | warning/critical | ar-aging ✓ | – | Finance tidak menerima; manajer satu-PT melihat piutang PT lain [V] |
| 9b | ar_overdue (salinan) | alert_service.py:91 — idem | ORANG assigned_sales_id | – | **KOSONG** | H | idem | ar-aging ✓ | – | – |
| 10 | ap_due | alert_service.py:165 — job: tagihan pemasok ≤ N hari jatuh tempo | KEBIJAKAN(manager) | vendor_bill.pay (finance) | isi | H | warning/critical | vendor-bills ✓ | – | Finance (pembayar) tidak menerima secara bawaan [V] |
| 11 | depreciation_due | alert_service.py:194 — job: penyusutan bulan lalu belum dijalankan | KEBIJAKAN(manager) | fixed_asset.run | **KOSONG** | H | warning | fixed-assets ✓ | – | Satu pesan untuk aset semua PT [V] |
| 12 | budget_alert | alert_service.py:226 — job: anggaran over/mendekati | KEBIJAKAN(manager) | budget.view/update | isi | H | warning/critical | budget ✓ | – | – |
| 13 | production_stalled | alert_service.py:275 — job: WO draft/released menua / bahan kurang | KEBIJAKAN(warehouse) | production.release/complete | isi | H | warning/critical | production ✓ | – | Admin Gudang tidak menerima bawaan [V] |
| 14 | ops_stalled | alert_service.py:319 — job: tugas WMS menganggur > N hari | KEBIJAKAN(warehouse) | wms.update | isi | H | warning | operations ✓ | – | idem |
| 15 | po_arrival | alert_ops_service.py:146,152,168 — penerimaan PO selesai (event GR + job) | KEBIJAKAN(manager) + KEBIJAKAN(warehouse) + ORANG sales pemilik pendingan | – (informasi) | isi | H | info/warning | purchasing ✓, operations ✓, orders ✓ | – | Salinan sales: `recipient_user=None` bila pelanggan tanpa sales → hanya admin yang melihat [V] |
| 16 | backorder_ready | alert_ops_service.py:240,251 — job/event: stok pendingan tersedia / terpenuhi | ORANG sales pemilik + KEBIJAKAN(manager) | order.update | isi | H | warning/info | orders ✓ | – | idem (yatim bila tanpa sales) |
| 17 | ar_due_soon | alert_ops_service.py:315,330 — job: piutang H-3/H-1/H/H+1 | ORANG assigned_sales_id + KEBIJAKAN(izin ar_receipt.create) | ar_receipt.create (finance), sales pemilik | isi | H | info/warning/critical | ar-aging ✓ | – | **Salinan tim sampai ke SEMUA sales PT** (sales memegang ar_receipt.create) — kebocoran yang diklaim ditutup FASE N [V] |
| 18 | restock_request | alert_ops_service.py:359 (restock_service) — sales minta repeat/restock dari SO → PR | PERAN(manager) | purchase_requisition.approve | isi | H | warning | purchase-requisitions ✓ | TIDAK | Finance pemegang PR approve tidak menerima [V] |
| 19 | approval_backlog | approval_reminder.py:104,113 — job harian: dokumen menunggu ≥ ambang (semua ~44 antrean) | PERAN(manager); eskalasi PERAN(admin) | izin pemutus tiap antrean (berbeda-beda) | isi | H | warning/critical | approval-inbox ✓ | – | Satu alamat "manager" untuk antrean cuti, gaji, kontrabon, tagihan, jurnal, dll. [V] |
| 20 | turn | turn_notification_service.py:163 — dokumen (SO/PO/retur jual/retur beli) pindah status | IZIN (per aturan TURN_MAP, minus kategori "pengawas" yang tak disebut) + pemilik | sesuai aturan | isi | E (+turn_marks) | info/warning | approvals ✓a, orders ✓, operations ✓, finance ✓a, purchase-orders ✓a, returns ✓, purchase-returns ✓ | res (tahap berikut) | Demo: giliran SO-0007 (masih waiting_approval) ditutup "tahap → waiting_approval" & tak dibuat ulang (cek stale sesudah resolve); akun yang dibuat sesudahnya (md, wh.admin, sample_admin) tak pernah menerima giliran lama [V] |
| 21 | escalation | escalation_service.py:185 — job: notifikasi warning+ belum dibaca > N jam | PERAN(rantai: sales/warehouse→manager→admin; per-orang→admin) | sesuai notifikasi asal | ikut asal | H | critical | ikut asal | menyalin action | Peran di luar rantai (finance, sales_admin, md, …) siaran perannya tak pernah naik [V] |
| 22 | ai_followup | ai_actions.py:288 — kartu Tanya KN "tagih/follow-up" disetujui | ORANG (sales tujuan) | customer.view | isi | U | warning | **customers ✗** | – | Klik → layar kosong desktop [V] |
| 23 | ai_report | ai_schedules.py:130,150 — laporan terjadwal Tanya KN selesai | ORANG pemilik jadwal | ai.view | isi | – | info | tanya-kn ✓ | – | – |
| 24 | ai_insight | ai_insights.py:129 — job anomali (penjualan turun, piutang, stok habis, PO telat) | PERAN[admin,manager(+finance/+warehouse_admin)]→orang + sales | – | isi | H/orang | warning/critical | tanya-kn ✓ | – | – |
| 25 | ai_card_second | ai_cards.py:1238 — kartu asisten kelas C menunggu orang kedua | ORANG (calon berkelas C) | ai + kontrol dua orang | isi | U | warning | tanya-kn ✓ | TIDAK | – |
| 26 | finance_case | finance_case_service.py:358 (kasus baru), finance_case_scan.py:130 (eskalasi SLA) | PERAN(manager); eskalasi PERAN(manager→admin) | finance_case.resolve (finance) | isi | U / H | warning/critical | finance-cases ✓ | **TIDAK** (action_type finance_case tak pernah di-resolve; demo 3 terbuka) | Finance tidak menerima kasus keuangan baru [V] |
| 27 | rfid_gate_alarm | rfid_incident_service.py:85 — gate merah menahan roll | PERAN(warehouse) | wms.update (ack, routers/rfid.py:757) | isi | U | critical | cs-rfid-gate ✓ | – | Admin Gudang tidak menerima [V] |
| 28 | rfid_reader_health | rfid_v2_health.py:86 — reader v2 tidak sehat (transisi aktif) | PERAN(warehouse_admin), PERAN(manager) | settings perangkat | **KOSONG** | U (efektif "sekali seumur", lihat T3) | warning | settings-devices ✓ | – | Gangguan kedua perangkat/aturan sama tak pernah diberitahukan [V] |
| 29 | rfid_gate_review | gate_review_service.py:215 — kasus antrean periksa gate | PERAN(warehouse_admin), PERAN(manager) | wms.update | **KOSONG** | U | warning/critical | cs-rfid-gate ✓ | – | lintas PT [V] |
| 30 | rfid_gate_rescan | gate_review_actions.py:231 — admin minta pindai ulang roll | PERAN(warehouse) | wms.scan | **KOSONG** | U | warning | cs-rfid-gate ✓ | – | lintas PT [V] |
| 31 | titipan_pesanan_batal | ar_receipt_service.py:427 — uang muka SO batal/kedaluwarsa jadi titipan | IZIN(payment_variance.decide) | payment_variance.decide | isi | U/orang | warning | advance-report ✓ | – | – |
| 32 | titipan_pesanan_batal_gagal | ar_receipt_service.py:427 — pemindahan ke titipan GAGAL | IZIN(payment_variance.decide) | idem | isi | U/orang | **danger** (tak dikenal) | advance-report ✓ | – | Severity non-baku → dihitung "info" oleh eskalasi/WA [V] |
| 33 | period_unlock_reclosed | period_unlock_service.py:274 — job: jendela buka periode berakhir | PERAN(admin) | periode/tutup buku (finance) | isi | H | warning/info | period-unlock ✓ | – | Finance (yang "Tutup Ulang") tidak menerima [D] |
| 34 | inspection_assigned | inspection_service.py:987 — SPK inspeksi ditugaskan | ORANG petugas | inspection.inspect | isi | U | info | inspections ✓ | – | – |
| 35 | revalidation_failed | rnd_revalidation_service.py:215 — uji ulang sample gagal | PERAN[md,manager]→orang | rnd.pic_decide | isi | U/orang | warning | rnd-samples ✓ | – | finance (rnd.decide) tidak; wajar [D] |
| 36 | interco_price_request | interco_price_service.py:158 — peran tanpa wewenang minta harga internal | IZIN(interco_price.set) | interco_price.set | **KOSONG** | U/orang | warning | **?view=internal-prices&… ✗** | – | Klik → layar kosong desktop; tab frontend `internal-prices` hanya admin di hubTabs [V/D] |
| 37 | penalty_draft | penalty_service.py:439 — nota denda usulan lahir | PERAN(manager) | penalty.issue/waive (finance juga) | isi | H | warning | payment-plans ✓ | TIDAK | finance tidak menerima [V] |
| 38 | payment_variance | payment_variance_service.py:794 — keputusan sensitif (hapus sisa/refund) selesai | PERAN(manager) | (informasi) | isi | H | warning | payment-plans ✓ | – | – |
| 39 | contra_bon_cycle | contra_bon_reminder.py:211 — jadwal tukar faktur pemasok | PERAN[finance,manager]→orang | contra_bon.create | isi | H/orang | info/warning | contra-bons ✓ | – | – |
| 40 | contra_bon_overdue | contra_bon_reminder.py:227 — kontrabon menunggu > SLA | PERAN(manager) | contra_bon.verify/approve (finance) | isi | H | warning | contra-bons ✓ | – | finance tidak menerima [V] |
| 41 | special_order_revision | special_order_phase2.py:280 — pelanggan minta revisi → sample baru | PERAN[md,manager]→orang | rnd.submit | isi | U/orang | warning | rnd-samples ✓ | – | – |
| 42 | special_order_proofing | special_order_phase2.py:975 — desain ACC → proofing otomatis | PERAN[md,manager]→orang | rnd.submit | isi | U/orang | info | rnd-proofing ✓ | – | – |
| 43 | amendment_approval | amendment_service.py:1053 (`_notify_approvers`, dipanggil :673, :725) — amandemen menunggu | PERAN(required_role); untuk override harga: loop manager, admin, finance | finance_amendment.approve / order.approve_price_edit | isi | U | warning | amendments ✓ | res (:1038) | **Loop 3 peran memakai ref sama → hanya peran pertama (manager) tercipta; finance tak pernah menerima** [V] |
| 44 | saga_lock_stuck | saga_lock_watch.py:77 — kunci saga menggantung | PERAN[admin]→orang | admin | isi | H/orang | warning/critical | settings-config ✓ | – | – |
| 45 | ocr_budget | goods_receipt_ocr_service.py:94 — anggaran OCR ≥ ambang | PERAN(admin) | settings | isi | cek ref manual | warning | **/?view=goods-receipts ✗** | – | Klik → layar kosong [V] |
| 46 | color_use_request | color_lock_service.py:94 — minta izin pakai warna eksklusif | PERAN(manager) | color.approve | isi | – | warning | **?view=color-library ✗ ⚠R** | TIDAK | **Manajer tidak pernah melihatnya** (link bukan id layar → disaring) [V] |
| 47 | color_use_decided | color_lock_service.py:133 — izin warna diputus | ORANG pengaju | – | isi | – | success/warning | ?view=color-library ✗ | – | Klik → layar kosong [V] |
| 48 | special_order_price_loss | od_pricing_service.py:165 — harga OD di bawah biaya kontrak | PERAN[manager]→orang | order.approve | isi | U/orang | warning | special-orders ✓ | – | – |
| 49 | campaign_bill_approval | marketing_cost_service.py:222 — tagihan vendor kampanye diajukan | PERAN(finance) | vendor_bill.approve (+aturan `vendor_bill.kampanye`) | isi | U | warning | accounts-payable ✓(menu hub) | res (ditandai read :259,:281) | manager (pemegang approve) tidak menerima [V] |
| 50 | mkt_review | marketing_service.py:230 — konten masuk review | PERAN[manager,admin]→orang | marketing.approve | isi | U/orang | info | mkt-calendar ✓ | – | finance (marketing.approve) tidak; minor |
| 51 | mkt_approved | marketing_service.py:234 — konten disetujui | ORANG PIC | – | isi | U | success | mkt-calendar ✓ | – | – |
| 52 | mkt_publish_due | marketing_service.py:383 — job: saatnya tayang | ORANG PIC; cadangan PERAN[manager]→orang | – | isi | U | info/warning | mkt-calendar ✓ | – | – |
| 53 | printer_stuck | printer_stuck_watch.py:62,71 — label tertahan > N menit tanpa printer | PERAN(warehouse_admin) + PERAN(manager) | wms.update | isi | U (efektif sekali per gudang) | warning | operations ✓ | – | **Printer mati kedua kalinya di gudang sama → tak ada pemberitahuan** [V] |
| 54 | export_schedule | export_schedule.py:81 (gagal), export_center.py:134 (siap) | ORANG pemilik | export | isi | – | warning/info | export-center ✓ | – | – |
| 55 | export_ready | export_center.py:127 — ekspor besar selesai | ORANG pemilik | export | isi | – | info | export-center ✓ | – | – |
| 56 | interco_payment_due | interco_service.py:1734 — job: jadwal bayar antar-PT ≤ N hari | PERAN(finance) | interco.settle | isi (payer) | E | info/warning | interco-transactions ✓ | – | – |
| 57 | interco_receipt_auto_fulfilled | interco_service.py:2640 — barang antar-PT diterima, SO terpenuhi otomatis | PERAN(sales_admin) | order.confirm | isi (buyer) | U | info | **pending-so ✗** (hanya HP sales) | – | Klik desktop → layar kosong [V] |
| 58 | rnd_sla_overdue | rnd_sla_service.py:156 — job: round sample lewat tenggat | PERAN(manager) | rnd.manage | isi | H | warning/critical | rnd-reports ✓ | – | MD (pelaksana R&D) tidak menerima [V] |
| 59 | rnd_sla_escalated | rnd_sla_service.py:165 — idem tier admin | PERAN(admin) | – | isi | H | critical | rnd-reports ✓ | – | – |
| 60 | so_override | so_override_service.py:480 (override admin :467; batal SO sales_orders_extra.py:946) | ORANG sales_team/sales_id/created_by | – | isi | – | info | orders ✓ | – | – |
| 61 | price_approval_pending | price_approval_service.py:146 — harga khusus menunggu ACC | PERAN(manager) | price_approval.approve (finance juga) | isi | U | warning | price-approvals ✓ | **TIDAK** (action_type price_approval_view tak di-resolve) | Pengaju tak diberi tahu saat approve/reject [V] |
| 62 | price_approval_superseded | routers/price_approvals.py:440 — aturan harga lama diganti | ORANG pengaju lama | – | isi | U | warning | price-approvals ✓ | – | – |
| 63 | price_approval_revoked | routers/price_approvals.py:538 — harga khusus diakhiri | ORANG pengaju | – | isi | U | warning | price-approvals ✓ | – | – |
| 64 | grn_claim | goods_receipt_close_service.py:196 — selisih GRN diputus klaim pemasok/makloon | PERAN(manager) | goods_receipt.approve | isi | U | warning | **/?view=goods-receipts&id=… ✗ ⚠R** | – | **Manajer tidak pernah melihatnya** [V] |
| 65 | internal_request_submitted | internal_request_service.py:258 — permintaan internal antar-PT diajukan | loop PERAN(admin), PERAN(manager), PERAN(sales_admin) | internal_request.convert/reject | isi (PT peminta) | U | info | internal-requests ✓ | TIDAK | **ref sama → hanya admin tercipta; Manajer & Admin Sales (pemilik antrean) tak pernah menerima** [V] |
| 66 | internal_request_decided | internal_request_service.py:501 — permintaan diputus | ORANG pemohon | – | isi | U | info | internal-requests ✓ | – | – |
| 67 | sample_payment_reapproval | sample_sale_service.py:423 — tagihan sample berubah > toleransi | PERAN(finance), PERAN(sample_admin) | sample_order.approve_payment | isi | U | warning | sample-orders ✓ | TIDAK | manager (pemegang izin) tidak; minor |
| 68 | sample_payment_refund | routers/sales_orders_extra.py:977 — SO sample berbayar dibatalkan | PERAN(finance) | – | isi | U | warning | sample-orders ✓ | – | – |
| 69 | design_claim_pending | design_ownership_service.py:207 — klaim desain diajukan | PERAN(manager) | design_ownership.decide (finance juga) | isi | U | info | rnd-designs ✓ | TIDAK | – |
| 70 | design_claim_decided | design_ownership_service.py:239 — klaim diputus | ORANG pengklaim; cadangan PERAN(manager) | – | isi | U | info | rnd-designs ✓ | – | – |
| 71 | od_cancel_credit_note | od_cancel_credit_note.py:69 — batal item OD yang SO-nya terbit → nota kredit | PERAN[finance]→orang | finance_amendment.review_credit_note | isi | U/orang | warning | orders ✓ (antrean ada di finance-desk) | – | link tidak ke antrean (doc-ref membantu) |
| 72 | inventory_drift | inventory_drift_watch.py:103 — selisih persediaan vs buku besar > ambang | IZIN(accounting.manage) | accounting.manage | isi | H/orang | warning/critical | general-ledger ✓ | – | contoh baik |
| 73 | logistics_delivered | logistics_service.py:736 (transisi :667, pickup :709) — surat jalan terkirim | PERAN[sales,sales_admin]→orang | sales pemilik SO + admin sales | isi | U/orang | success | orders ✓ | – | **Semua sales PT menerima pengiriman pelanggan rekan** [V] |
| 74 | logistics_failed | idem — gagal kirim | idem | idem | isi | U/orang | warning | orders ✓ | – | idem |
| 75 | po_close_settlement | po_close_settlement_service.py:87 — PO ditutup-kurang ber-tindak-lanjut finance | PERAN(finance) | vendor_bill/ap | isi | U | warning | purchasing ✓ (+action_id) | – | – |
| 76 | credit_override_requested | credit_override_service.py:99 — izin kredit diajukan | IZIN(credit_override.approve) | credit_override.approve | isi | U/orang | warning | credit-overrides ✓ | TIDAK | contoh baik alamat; tidak ditutup |
| 77 | credit_override_decided | credit_override_service.py:117 — izin kredit diputus | ORANG pengaju | – | isi | – | info | customers-crm ✓ | – | – |
| 78 | design_lifecycle | design_studio_service.py:757 (transisi :495, hold :528, umpan balik :665) | ORANG pemilik desain; tanpa pemilik → PERAN[designer]→orang; desainer→PERAN[manager,admin]→orang | rnd/design | isi | U/orang | info | rnd-designs ✓ | – | – |
| 79 | bank_rule_suggested | bank_recon_service.py:1480 — pola mutasi dicocokkan manual ≥ N× | PERAN(manager) | cash.create (decide aturan) — finance | isi | U | info | **/finance/bank-reconciliation ✗ ⚠R** | – | **Tak terlihat oleh manajer; finance tak dialamati** [V] |
| 80 | interco_return_incoming | return_disposition_service.py:191 — retur internal masuk ke PT pemasok | PERAN(warehouse_admin), PERAN(admin), PERAN(finance) | interco.receive/decide_rolls | isi | E | warning | interco-transactions ✓ | – | – |
| 81 | return_supplier_deadline | return_disposition_service.py:466 — job: batas retur supplier dekat | idem | interco.decide_rolls | isi | E | info/warning | interco-transactions ✓ | – | – |
| 82 | design_ai_comment | design_gallery_service.py:646 — komentar arahan ilustrasi AI | PERAN[designer]→orang (atau manager,admin) | – | isi | U/orang | info | rnd-designs ✓ | – | Semua desainer, bukan pemilik desain (beda dengan DESIGN-06) [V] |
| 83 | makloon_claim | makloon_claim_service.py:87 — klaim selisih langkah makloon dibuka | loop PERAN(roles Aturan Persetujuan; bawaan manager, admin) | makloon_order.claim_approve | isi | U | warning | makloon-orders ✓ | res (:273,:297) | **ref sama untuk semua peran → hanya peran pertama** [V] |
| 84 | makloon_claim_approval | makloon_claim_service.py:141 — usulan tindakan klaim | idem | idem | isi | U | warning | makloon-orders ✓ | res | idem [V] |
| 85 | interco_settlement_idle | interco_reminder.py:147 (manual), :169 (job) — saldo antar-PT menganggur | PERAN(manager) | interco.settle (finance juga) | isi | H / U(manual) | warning | interco-transactions ✓ | – | Tombol manual hampir selalu "ter-dedupe" (siaran tak pernah read=True) [V] |
| 86 | po_variance_decision | po_variance_task_service.py:85,90 — selisih terima PO di luar toleransi | ORANG MD penanggung jawab; cadangan PERAN(md) | purchase_order.update | isi | U | warning | purchasing ✓ | – | – |
| 87 | po_variance_finance | po_variance_task_service.py:94 — idem, PO ber-DP/tagihan | PERAN(finance) | – | isi | U | warning | purchasing ✓ | – | – |
| 88 | outbound_escalation | routers/outbound_picking.py:353 — petugas eskalasi tugas ambil | PERAN(manager), PERAN(warehouse_admin) | wms (resolve-escalation) | isi | U | warning | **outbound ✗ ⚠R** | – | **Manajer & Admin Gudang tak pernah melihatnya** [V] |
| 89 | so_qc_requested | routers/sales_orders.py:812 — SO dibuat dengan permintaan QC | IZIN(qc.inspect) | qc.inspect | isi | U/orang | warning | inspections ✓ | – | contoh baik |
| 90 | special_order_item_cancelled | routers/special_orders.py:1013 — item OD dibatalkan | PERAN[md]→orang | – | isi | U/orang | info/warning | special-orders ✓ | – | – |

## Ringkasan pengalamatan (90 jenis)
* Per orang lewat IZIN: 13 (low_stock, reservation_expiring, order_approval, order_split, po_stage_stuck,
  special_order_approval, titipan×2, interco_price_request, inventory_drift, credit_override_requested, so_qc_requested, turn).
* Per orang lewat NAMA PERAN (`create_addressed(roles=…)`): 14.
* Siaran satu dokumen ke NAMA PERAN (`recipient_role`): 38.
* `reminder_policy` (bawaan nama peran, bisa diubah per PT): 6 murni + 3 campuran (po_arrival, backorder_ready, ar_due_soon).
* Per orang lewat id (pemilik/pengaju/petugas): 16.
* `recipient_role="all"`: 0 (tidak ada panggilan tersisa yang jatuh ke bawaan "all").

## Antrean persetujuan (approval_backlog_service.QUEUES) tanpa notifikasi ke penyetuju saat masuk antrean
cash_advance, cash_advance_settlement, hr_leave, hr_overtime, hr_payroll, incentive_sheet, landed_cost, journal_proposal,
transfer, cycle_count, rnd_spec, rnd_sample (hanya SLA telat ke manajer), vendor_bill (non-kampanye), contra_bon_verify /
contra_bon_approve / contra_bon_dispute (hanya lewat SLA ke manajer), interco, interco_return (hanya pemberitahuan
penerima), period_unlock, makloon_loss, sales_return_exception, inspection_hold, design_request, payment_variance,
so_verify, purchase_requisition (hanya PR dari restock SO). Semua hanya tertangkap `approval_backlog` harian ke
"manager".

#!/usr/bin/env python3
"""INV-ATOMIC-01 — endpoint tulis multi-koleksi memakai klaim atomik (T-01 Opsi B, saga).

Keputusan 2026-09: TANPA replica set/transaksi Mongo. Endpoint yang menulis ≥2 koleksi
substantif wajib (a) `atomic_claim.claim()` sebelum tulisan turunan + tulisan akhir
mencabut `saga_lock` (`finish_set` / `$unset`), ATAU (b) CAS: `find_one_and_update`
induk berprasyarat `status` + tulisan turunan idempoten, ATAU (c) alasan tertulis di
`REVIEWED` (≥20 huruf), ATAU (d) `unit`: jalur tulisnya diganti unit blueprint yang belum
selesai. Sisanya "BELUM DITINJAU" — angkanya RATCHET: hanya boleh turun dari
`BASELINE_UNREVIEWED`; entri `REVIEWED` yang fungsinya tak lagi berpola → MERAH.

PK-33 (DB-01): kunci `REVIEWED` = (berkas router, "METODE /path persis") dan dicocokkan
SAMA PERSIS — entri `/x` tidak lagi menutupi `/x/{id}/go`, dan dua metode pada path yang
sama adalah dua entri. Mekanisme `claim`/`cas` juga sah bila polanya ada di fungsi
pembantu modul router yang sama yang dipanggil endpoint (satu tingkat). Mekanisme `unit`
sah hanya bila ID-nya ada di `docs/blueprint/INDEKS_UNIT.md` dan statusnya di
`docs/blueprint/STATUS.md` belum `selesai`/`tervalidasi` (begitu unit selesai → MERAH
sampai diganti mekanisme nyata).

Pakai:  python3 scripts/guardrails/verify_atomic_claim.py
        python3 scripts/guardrails/verify_atomic_claim.py --self-test
"""
from __future__ import annotations

import ast
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import Guard, BACKEND, ROOT, G, R, X  # noqa: E402
import inventaris_multi_koleksi as inv  # noqa: E402

# Baseline "BELUM DITINJAU" saat penjaga lahir (2026-09-05). Turunkan angka ini setiap
# kali satu endpoint selesai ditinjau — jangan pernah dinaikkan.
BASELINE_UNREVIEWED = 0

# (berkas router, "METODE /path persis") → (mekanisme, alasan[, rujukan layanan]).
# mekanisme ∈ MECHS (lihat di bawah REVIEWED). `unit`: alasan berbentuk "<ID unit>: <alasan ≥ 20 huruf>".
REVIEWED: dict[tuple[str, str], tuple[str, str]] = {
    # ── Tanya KN F1 (2026-09-27) ────────────────────────────────────────────────────────
    ("ai_analytics.py", "POST /schedules/{schedule_id}/run"): ("none", "laporan terjadwal manual: hasil template (ai_results baru, id acak) + riwayat run append-only + notifikasi log + $set last_run_* satu dokumen jadwal; tidak ada saldo/status bisnis; ulangan hanya membuat run baru"),
    ("ai_analytics.py", "POST /facts/rebuild"): ("none", "bangun ulang tabel turunan fact_sales_lines (delete_many+insert_many per SO, idempoten; ulangan menghasilkan baris identik) + audit append-only; tidak menyentuh dokumen bisnis/saldo"),
    # ── Audit 2026-09-22 — 2 endpoint baru ditinjau ─────────────────────────────────────
    ("data_hygiene.py", "POST /data-hygiene/run"): ("none", "pembersihan master (kota/provinsi) per dokumen: update_one $set nilai ternormalisasi + log append-only + ringkasan run; idempoten (ulangan menulis nilai sama), tidak ada saldo/status bersama"),
    ("settings.py", "DELETE /payment-terms/{term_id}"): ("none", "DELETE: satu find_one_and_update payment_terms $set active=False (idempoten) ATAU revert baris khusus PT lewat entity_master_service (satu dokumen); tidak ada koleksi kedua ber-saldo"),
    # ── Audit 2026-09-21 (sesi 3) — 16 endpoint ditinjau; alasan per baris ─────────────
    ("inbound_scan_label.py", "POST /inbound/tasks/{task_id}/scan-label"): ("service_cas", "find_one_and_update wms_tasks berprasyarat status hidup + $inc received_qty/qty_rolls_scanned (bukan $set hasil baca); kalah → roll baru dihapus (kompensasi) + 409 (GRN Fase 1: dipindah ke layanan)", "receiving_roll_service.attach_roll_to_task"),
    ("inbound_scan_label.py", "POST /inbound/rolls/{roll_id}/confirm-measure"): ("cas", "find_one_and_update inventory_rolls berprasyarat status receiving + actual_task_qty seperti dibaca → 409; selisih ke wms_tasks via $inc berprasyarat status hidup"),
    ("inbound_scan_label.py", "POST /inbound/rolls/{roll_id}/putaway"): ("cas", "prasyarat status receiving diteruskan ke penulis bin tunggal `location_service.place_roll(…, cas={\"status\": \"receiving\"})` = filter update_one inventory_rolls (matched 0 → 409 bila kalah); bin_id tugas idempoten ($set nilai sama) — PK-33: CAS pindah ke layanan"),
    ("inbound_scan_label.py", "POST /inbound/rolls/{roll_id}/tag"): ("none", "satu koleksi: encode_tag menulis rfid_tags + rfid_tag_id roll; tag ganda ditolak oleh rfid_service (EPC unik) — tak ada saldo bersama"),
    ("inbound_scan_label.py", "DELETE /inbound/rolls/{roll_id}/scan"): ("service_cas", "DELETE: delete_one inventory_rolls berprasyarat status receiving (deleted_count 0 → 409) SEBELUM tag/klaim nomor roll/tugas disentuh; received_qty/qty_rolls_scanned tugas dikurangi $inc berprasyarat status hidup lalu dijepit ≥ 0 — PK-33: hapus bersyarat pindah ke layanan", "receiving_roll_service.undo_receiving_roll"),
    ("sample_sales.py", "POST /outbound/tasks/{task_id}/cut-sample"): ("service", "klaim wms_tasks (status created|picking) sebelum roll induk dipotong; CAS roll induk length_remaining ≥ take; finish_set status packing", "sample_sale_service.cut_sample_task"),
    ("special_orders.py", "POST /special-orders/{order_id}/procure"): ("none", "auto_procure idempoten: menolak bila linked_po_id/linked_pr_id sudah ada (ODError 400); PR/PO lahir lewat generator nomor atomik; pemanggilan ganda → yang kedua 400"),
    ("special_orders.py", "POST /special-orders/{order_id}/route"): ("none", "route_on_approve idempoten per jenis (design_request_id/sample_ids sudah ada → dilewati); dokumen turunan tidak digandakan"),
    ("special_orders.py", "POST /special-orders/{order_id}/approve"): ("cas", "tingkat menengah: update_one berprasyarat status pending_approval + approval_level_current seperti dibaca → 409; tingkat akhir lewat transition_status CAS status saat ini (KN-B10)"),
    ("special_orders.py", "POST /special-orders/{order_id}/lock-price"): ("service", "update_one special_orders berprasyarat price_locked != True (matched_count 0 → ODError) sebelum produk/spec disentuh; kunci harga = satu penulis", "special_order_phase2.lock_price"),
    ("special_orders.py", "POST /special-orders/{order_id}/items/{item_id}/cancel"): ("service", "FE-01 batal item OD (2026-10-21): semua syarat dicek dulu; baris SO dibatalkan lewat klaim sales_orders (prasyarat status seperti dibaca, finish_set); PO/MKO/sample/permintaan desain dibatalkan lewat layanan masing-masing (status batal dilewati); penanda item batal = update_one berprasyarat item.status != cancelled → pemanggil kedua 409", "so_line_cancel_service.cancel_line"),
    ("special_orders.py", "POST /special-orders/{order_id}/prepare-shipment"): ("none", "membuat SO turunan hanya bila linked_sales_order_id kosong (cek + tulis satu dokumen); pemanggilan ganda → 400 sudah ada"),
    ("rnd.py", "POST /rnd/samples/{sample_id}/decide"): ("service", "decide_sample memakai so-style transition berprasyarat status (md_samples) sebelum keputusan pelanggan/keputusan OD disalin; amx.record idempoten per (stage, doc)", "rnd_sample_service.decide_sample"),
    ("data_hygiene.py", "POST /data-hygiene/location/{collection}/{doc_id}"): ("none", "satu update_one field lokasi (kota/provinsi) pada master + satu baris log append-only; tidak ada saldo/status bersama, ulangan menulis nilai sama"),
    ("marketing.py", "PATCH /marketing/campaigns/{cid}"): ("none", "PATCH satu dokumen mkt_campaigns ($set field yang dikirim) — tidak ada koleksi kedua ber-saldo"),
    ("marketing.py", "PATCH /marketing/accounts/{aid}"): ("none", "PATCH satu dokumen mkt_accounts ($set) — tidak ada koleksi kedua ber-saldo"),
    ("sample_orders.py", "POST /sample-orders/{order_id}/confirm"): ("cas", "so_transition CAS status $in [approved] → confirmed; create_outbound_tasks_for_order dedupe per order+product; recompute_so_status idempoten"),
    ("outbound_picking.py", "POST /outbound/tasks/{task_id}/resolve-escalation"): ("cas", "T-01 Langkah 1: find_one_and_update berprasyarat escalation.status $nin [resolved,resolving] → resolving (2026-09-05)"),
    ("inbound_receiving.py", "POST /inbound/tasks/{task_id}/complete"): ("service", "klaim wms_tasks sebelum roll/mutasi/PO ditulis; tulisan akhir $unset saga_lock (GRN Fase 1: logika dipindah ke layanan)", "inbound_complete_service.complete_task"),
    # BTP-2 — isi batal pindah ke `so_cancel_service.execute_cancel` (dipanggil `submit` dan `decide`); permintaan baru
    # dipasang lewat klaim bersyarat `cancel_request.status != pending` + finish_set.
    ("sales_orders_extra.py", "POST /sales-orders/{order_id}/cancel"): ("service", "klaim sales_orders sebelum roll dilepas; so_transition CAS + $unset (di layanan, dipanggil lewat submit)", "so_cancel_service.execute_cancel"),
    ("so_approvals.py", "POST /sales-orders/{order_id}/approvals/{approval_id}/decide"): ("claim", "klaim sales_orders per entri approval ($elemMatch pending); release di akhir"),
    ("transfers.py", "POST /transfers/{transfer_id}/approve"): ("claim", "klaim warehouse_transfers sebelum kepemilikan roll + jurnal; finish_set"),
    ("transfers.py", "POST /transfers/{transfer_id}/reject"): ("claim", "klaim warehouse_transfers sebelum roll dilepas; finish_set"),
    ("transfers.py", "POST /transfers/{transfer_id}/status"): ("claim", "klaim warehouse_transfers sebelum dispatch/receive roll; finish_set"),
    ("cycle_count.py", "POST /cycle-count/sessions/{session_id}/approve"): ("claim", "klaim cycle_count_sessions sebelum selisih diterapkan ke roll; finish_set"),
    ("purchase_orders_extra.py", "POST /purchase-orders/{po_id}/close"): ("cas", "find_one_and_update induk berprasyarat status di pembantu modul yang sama `short_close_po` (PK-33 B.3); wms_tasks update_many idempoten"),
    ("purchase_orders_extra.py", "POST /purchase-orders/{po_id}/cancel"): ("cas", "find_one_and_update induk berprasyarat status; wms_tasks update_many idempoten"),
    ("vendor_bills.py", "POST /vendor-bills/{bill_id}/pay"): ("service", "PK-05 — niat bayar: periksa tanpa tulis → klaim faktur → niat pending → faktur (CAS per alokasi, id pembayaran turunan) → kas (id turunan) → jurnal tahan-gagal → selesai+lepas", "ap_payment_service.pay_payable"),
    ("contra_bons.py", "POST /contra-bons/{cb_id}/pay"): ("service", "PK-05 — niat bayar kontrabon: klaim berprasyarat status+sisa, alokasi faktur idempoten, kas turunan, dokumen berversi, jurnal potongan tahan-gagal", "ap_payment_service.pay_payable"),
    ("contra_bons.py", "POST /contra-bons/{cb_id}/pay-from-bank-line/{line_id}"): ("service", "PK-05 — sama dengan bayar kontrabon; kunci niat = bank_line:<id baris>", "ap_payment_service.pay_payable"),
    ("interco.py", "POST /interco/transactions/{interco_id}/confirm"): ("service", "PK-06 — periksa jurnal KEDUA PT (preflight_twin) → klaim dokumen penjual berprasyarat draft → status confirmed → jurnal per sisi tahan-gagal → release", "interco_service.confirm"),
    ("interco.py", "POST /interco/returns/{ret_id}/approve"): ("service", "PK-06 — periksa jurnal kedua PT + transaksi asal tidak gagal → klaim dokumen pengembali berprasyarat draft → approved → jurnal per sisi → release", "interco_return_service.approve"),
    ("interco.py", "POST /interco/settlements"): ("service_cas", "PK-06 — settlement pending ber-id dari kunci; sisa tiap dokumen dinaikkan CAS (status terbuka + settlement_ids + Σ ≤ nilai), gagal → dikembalikan; kas kembar idempoten; jurnal per sisi", "interco_service._apply_settlement_rows"),
    ("interco.py", "POST /interco/refunds"): ("service_cas", "PK-31 — refund pending ber-id dari kunci; refund_paid tiap dokumen kembar dinaikkan CAS (status bukan draf/batal + refund_ids + refund_paid ≤ retur + lunas − nilai), gagal → dikembalikan; kas kembar idempoten; jurnal per sisi", "interco_service._apply_refund_rows"),
    ("sales_orders_extra.py", "POST /sales-orders/{order_id}/approve"): ("cas", "so_transition CAS status $in expected_from; set_order_rolls_status idempoten"),
    # Trial 22 Okt (E8) — inti dipindah ke layanan supaya "Periksa & lepas ke gudang" memakai logika yang sama.
    ("sales_orders_extra.py", "POST /sales-orders/{order_id}/submit-for-approval"): ("service_cas", "so_transition CAS status $in expected_from; set_order_rolls_status idempoten", "so_lifecycle_service.submit_core"),
    ("sales_orders_extra.py", "POST /sales-orders/{order_id}/confirm"): ("service_cas", "so_transition CAS; create_outbound_tasks_for_order dedupe per order+product", "so_lifecycle_service.confirm_core"),
    ("sales_orders_extra.py", "POST /sales-orders/{order_id}/release-reservation"): ("claim", "klaim sales_orders sebelum roll dilepas; tulisan akhir finish_set (draft)"),
    ("sales_orders_extra.py", "POST /sales-orders/{order_id}/items/{product_id}/reallocate"): ("claim", "klaim sales_orders sesudah validasi, sebelum roll baru direservasi/roll lama dilepas; release bila reserve gagal; finish_set"),
    ("sales_orders_extra.py", "POST /sales-orders/{order_id}/items/{product_id}/release-rolls"): ("claim", "klaim sales_orders sebelum roll dilepas + mutasi ditulis; tulisan akhir finish_set (+$push reservation_releases)"),
    ("vendor_bills.py", "POST /vendor-bills/{bill_id}/cancel"): ("claim", "klaim vendor_bills berprasyarat status+amount_paid sebelum jurnal dibalik; mark_failed bila reversal gagal; finish_set status cancelled"),
    ("payment_variance.py", "POST /payment-variances/{decision_id}/reverse"): ("service", "klaim payment_variance_decisions (status != reversed) di service sebelum payments SO/deposit/kas/JE dibalik; finish_set", "payment_variance_service.reverse_decision"),
    ("purchase_returns.py", "POST /purchase-returns/{return_id}/reverse"): ("service", "klaim purchase_returns di service sesudah guard, sebelum JE/roll/AP/kas; finish_set", "purchase_return_service.reverse_settlement"),
    ("sales_returns.py", "POST /sales-returns/{return_id}/reverse"): ("service", "klaim sales_returns di service sesudah guard, sebelum JE/roll/kas/CN; finish_set", "return_service.reverse_settlement"),
    ("sales_returns.py", "POST /sales-returns/{return_id}/reverse-writeoff"): ("service", "klaim sales_returns sesudah target roll scrap ditentukan, sebelum JE write-off dibalik/roll dipulihkan/mutasi; finish_set", "return_service.reverse_writeoff"),
    ("sales_returns.py", "POST /sales-returns/{return_id}/relocate"): ("none", "L08 LN-081: dinonaktifkan — selalu 409 tanpa menulis apa pun"),
    ("sales_returns.py", "POST /sales-returns/{return_id}/journey/scan"): ("service_cas", "find_one_and_update sales_returns berprasyarat status + journey_rev (CAS) → 409; roll inventori tidak disentuh", "return_journey_service.scan"),
    ("sales_returns.py", "POST /sales-returns/{return_id}/quarantine/release"): ("service", "klaim sales_returns (quarantine_released != True) sesudah roll karantina & keputusan ditentukan, sebelum roll/JE write-off/mutasi; finish_set quarantine_released", "return_service.release_quarantine"),
    ("crm_omnichannel.py", "POST /crm/leads/{lead_id}/convert"): ("service", "klaim crm_leads (customer_id kosong) sesudah validasi lead/pelanggan tujuan, sebelum customers/interaksi ditulis; finish_set customer_id+stage won", "crm_omnichannel_service.convert_lead"),
    ("purchase_returns.py", "POST /purchase-returns/{return_id}/goods-back"): ("service", "klaim purchase_returns (supplier_status != goods_back) sesudah assert_transition, sebelum roll/mutasi/balance; finish_set supplier_status", "purchase_return_service.goods_back"),
    ("putaway_orders.py", "POST /putaway-orders/{order_id}/resolve-exception"): ("service", "klaim putaway_orders sesudah target item exception ditentukan, sebelum roll/tag/jejak/balance/BTG; finish_set status", "putaway_order_service.resolve_exception"),
    ("purchase_returns.py", "POST /purchase-returns/{return_id}/ship-to-supplier"): ("service", "klaim purchase_returns (supplier_status != shipped) sesudah assert_transition, sebelum roll dikarantina/balance; finish_set supplier_status", "purchase_return_service.ship_to_supplier"),
    ("invoices.py", "POST /sales-orders/{order_id}/simulate-payment"): ("none", "PK-19 (SL-05) — dimatikan: selalu 410 sesudah pemeriksaan izin, tidak menulis apa pun"),
    ("closing.py", "POST /finance/closing/{closing_id}/reopen"): ("service", "klaim period_closings (status closed) sebelum JE penutup di-void; finish_set status reopened", "closing_service.reopen_period"),
    ("closing.py", "POST /finance/closing/{closing_id}/reclose"): ("service", "klaim period_closings (status closed) sebelum JE lama di-void & JE baru dibuat; finish_set angka penutup", "closing_service.reclose_period"),
    ("transfers.py", "DELETE /transfers/{transfer_id}"): ("claim", "DELETE: klaim warehouse_transfers (status hidup) sesudah guard, SEBELUM roll dilepas; finish_set status cancelled dalam find_one_and_update"),
    # PM-T4 — terima setoran titipan tunai sales: periksa tanpa tulis → klaim cash_deposits (status diajukan) → niat
    # (id kas tetap) → titipan naik bersyarat + penanda deposit_ids (ulang tidak ganda) → kas tahan-gagal → finish_set.
    ("cash_holdings.py", "POST /cash-deposits/{dep_id}/receive"): ("service", "PM-T4 — klaim cash_deposits berprasyarat status diajukan sebelum titipan (cash_holdings) dinaikkan bersyarat deposited_amount ≤ amount − alokasi dengan penanda deposit_ids; kas lewat create_cash ber-id tetap dari niat; finish_set status diterima", "cash_holding_service.terima_setoran"),
    # Kas & Bank 1 (Tugas 4) — Pindah Dana: periksa tanpa tulis (rekening, periode, akun jurnal, rekonsiliasi) → klaim
    # fund_transfers berprasyarat status → kas lewat create_cash ber-id tetap per `seq` (kirim ulang = kas yang sama) /
    # pembalik kas lewat post_durable → finish_set. Buat (`POST ""`) memakai `_terbit` yang sama.
    ("fund_transfers.py", "POST /{transfer_id}/approve"): ("service", "klaim fund_transfers berprasyarat status menunggu_persetujuan sebelum kas kirim/biaya/terima terbit (id kas tetap per seq); finish_set status dalam_perjalanan/selesai", "fund_transfer_service._terbit"),
    ("fund_transfers.py", "POST /{transfer_id}/receive"): ("service", "klaim fund_transfers berprasyarat status dalam_perjalanan sebelum kas masuk rekening tujuan terbit (id kas tetap seq terima); finish_set status selesai", "fund_transfer_service.terima"),
    ("fund_transfers.py", "POST /{transfer_id}/cancel"): ("service", "klaim fund_transfers berprasyarat status hidup (atau batal yang pembaliknya tertunda) sebelum niat batal ditulis dan tiap kas dibalik lewat post_cash_void tahan-gagal lalu void; gagal → batal_gl_status failed (Posting Gagal), kunci dilepas; finish_set", "fund_transfer_service.batal"),
    ("ar_receipts.py", "POST /ar-receipts/{receipt_id}/void"): ("service", "klaim ar_receipts (status != void) sebelum keputusan selisih/payments SO/kas/deposit dibalik; release bila reverse_decision gagal; finish_set status void", "ar_receipt_service.void_receipt"),
    ("inventory.py", "POST /inventory/initial-stock"): ("compensate", "roll baru per permintaan (tak ada dokumen bersama); mutasi+rebuild di try, except → rollback_initial_stock menghapus roll & mutasi yang lahir"),
    ("inbound_receiving.py", "POST /inbound/tasks/{task_id}/resolve-escalation"): ("cas", "find_one_and_update wms_tasks berprasyarat escalation.status != resolved → 409 bila kalah (pola outbound)"),
    # ── FIX-3a (9 Nov 2026) — tabel transisi tugas barang masuk (`services/inbound_task_state.py`) ──────────────
    ("inbound_receiving.py", "POST /inbound/tasks/{task_id}/scan-receive"): ("cas", "FIX-3a: inbound_task_state.transition = find_one_and_update wms_tasks berprasyarat status asal (daftar-izin) + received_qty seperti dibaca → 409 bila kalah; warehouses/cycle_count_sessions hanya DIBACA (validasi bin & pembekuan), audit append-only"),
    ("inbound_receiving.py", "POST /inbound/tasks/{task_id}/escalate"): ("cas", "FIX-3a: inbound_task_state.transition = find_one_and_update wms_tasks berprasyarat status ∈ daftar-izin + bukan dihitung GRN → 409; koleksi lain hanya dibaca (mode GRN) + audit append-only"),
    ("putaway_orders.py", "POST /putaway-orders/{order_id}/confirm-arrival"): ("service", "klaim putaway_orders di service sebelum bulk roll/tag/mutasi; finish_set", "putaway_order_service.confirm_arrival"),
    # ── PREP-C (2026-11-08) — draf otomatis & tiba bertahap per trip ──────────────────────
    ("putaway_orders.py", "POST /putaway-orders/{order_id}/dispatch"): ("service", "klaim putaway_orders (status open) sebelum roll → in_transit_transfer; gagal satu roll → kompensasi roll yang sudah pindah + release; finish_set status in_transit", "putaway_order_service.dispatch"),
    ("putaway_orders.py", "POST /putaway-orders/{order_id}/publish"): ("service", "klaim putaway_orders (status draft + draft_rev) sesudah semua validasi kesiapan, sebelum roll diklaim (active_movement CAS per roll); gagal → klaim roll dilepas + release; finish_set status open", "putaway_draft_service.publish"),
    ("putaway_orders.py", "POST /putaway-orders/{order_id}/arrival-trips"): ("service", "klaim putaway_orders (status open/in_transit/partially_received) sebelum roll/tag/mutasi ber-id deterministik; trip ber-passage_id/client_trip_id idempoten; gagal → release; finish_set status turunan item", "putaway_arrival_service.confirm_arrival_trip"),
    ("putaway_orders.py", "POST /putaway-orders/{order_id}/close"): ("service", "klaim putaway_orders sesudah validasi alasan/aksi, sebelum adopsi roll & sisa → transit/exception; gagal → release; finish_set status akhir", "putaway_arrival_service.close_remaining"),
    ("sales_orders.py", "POST /sales-orders"): ("compensate", "id SO baru per permintaan (tak ada dokumen bersama); roll direservasi lebih dulu dan DILEPAS (release_order_rolls) di except bila insert gagal — kompensasi saga"),
    ("rfid.py", "POST /rfid/ingest"): ("service", "rfid_reads append-only (id baru per baca) + rfid_tags.last_seen idempoten + rfid_devices.status; tidak ada saldo/stok/status dokumen — aman diulang, tak butuh kunci"),
    ("sales_returns.py", "POST /sales-returns/{return_id}/rolls/{roll_id}/transfer-ownership"): ("service", "klaim sales_returns sesudah semua validasi (roll/entitas/E9.3), sebelum roll direservasi/ownership dipindah/JE; release bila CAS roll kalah atau engine gagal; finish_set + $push ownership_transfers", "return_service.transfer_return_roll_ownership"),
    ("transfers.py", "POST /transfers"): ("compensate", "POST: id transfer baru per permintaan; reservasi roll + insert dokumen dalam satu try, except → release_wh_transfer_rolls melepas reservasi parsial (kompensasi saga)"),
    ("wms.py", "POST /wms/tasks"): ("compensate", "POST: id tugas baru per permintaan; inbound manual → create_inbound_roll dalam try, except → rollback_task_shell menghapus tugas tanpa roll (kompensasi saga)"),
    ("outbound_picking.py", "POST /outbound/tasks/{task_id}/scan-pick"): ("cas", "FIX-3b: _ots.transition (outbound_task_state) = find_one_and_update wms_tasks berprasyarat status ∈ daftar-izin scan_pick + picked_qty sama seperti saat dibaca → 409 STATE_CHANGED bila kalah; SO status diturunkan sesudahnya (idempoten)"),
    # ── FIX-3b (9 Nov 2026) — batal perbaikan saat barang di luar (B2b FLW-OUT-11) ───────────
    ("repair_orders.py", "POST /repair-orders/{ro_id}/receive-back"): ("none", "FIX-3b: per roll update_one inventory_rolls berprasyarat repair_open = RO & status wip (CAS, ulangan = no-op) + mutasi hanya untuk roll yang benar-benar berubah; status dokumen lewat _push CAS status 'returning' (kalah → RepairError); tanpa saldo uang/jurnal"),
    ("outbound_picking.py", "POST /outbound/tasks/{task_id}/dispatch"): ("service", "klaim wms_tasks (status dispatchable) sesudah validasi qty, sebelum roll dikirim/surat jalan; release bila ship_order_rolls gagal; finish_set status+shipped_qty", "shipment_service.dispatch_task"),
    ("inbound_receiving_extra.py", "POST /inbound/tasks/{task_id}/qc-decision"): ("service", "klaim wms_tasks (status qc_pending) sesudah validasi qty/grade/disposisi, sebelum roll karantina dikonsumsi/retur/balance; mark_failed bila gagal; finish_set status+jejak QC", "qc_service.process_qc_decision"),
    # ── PREP-F (9 Nov 2026) — printer label CP30EN ──────────────────────────────────────
    ("rfid_printers.py", "POST /rfid/device-jobs/claim"): ("service_cas", "klaim lease per job: find_one_and_update rfid_print_jobs berprasyarat status queued|printing + lease kosong/kedaluwarsa + tanpa item started (pemenang tunggal); redelivery tanpa tulis; sapuan efek tertunda idempoten (tag pending_print→active, label print unik per job+roll, riwayat ber-kunci)", "rfid_printer_protocol.claim_jobs"),
    ("rfid_printers.py", "POST /rfid/print-jobs/{job_id}/items/{item_id}/resolve"): ("service", "update_one rfid_print_jobs dengan arrayFilters berprasyarat status item seperti dibaca (modified_count≠1 → 409) SEBELUM efek; pensiun tag = find_one_and_update berprasyarat status hidup; efek konfirmasi idempoten (apply_item_effects); job cetak ulang lewat create_print_job (EPC baru)"),
    ("rfid_printers.py", "POST /rfid/rolls/{roll_id}/replace-tag"): ("service_cas", "tolak bila roll dalam perpindahan / tag masih di item terbuka; pensiun tag lama = find_one_and_update berprasyarat status hidup (kalah → 409); tag baru via encode_tag CAS rfid_tag_id kosong; gagal → tag lama dipulihkan (kompensasi)", "rfid_print_service._retire_live_tag"),
    ("rfid.py", "POST /rfid/tags/encode"): ("service_cas", "insert rfid_tags lalu CAS inventory_rolls (find_one_and_update rfid_tag_id kosong → tag); kalah → tag baru dihapus (kompensasi) + 409 STATE_CHANGED", "rfid_service.encode_tag"),
    ("rfid.py", "DELETE /rfid/tags/{tag_id}"): ("service_cas", "DELETE: find_one_and_update rfid_tags berprasyarat status active → retired; kalah → 409; roll dilepas hanya bila rfid_tag_id masih menunjuk tag ini (idempoten)", "rfid_service.retire_tag"),
    ("wms.py", "POST /wms/tasks/{task_id}/advance"): ("cas", "find_one_and_update wms_tasks berprasyarat status == status saat dibaca → 409 STATE_CHANGED; jalur dispatched didelegasikan ke dispatch_task (klaim sesi 12)"),
    ("rfid.py", "POST /rfid/verify-sessions/{session_id}/complete"): ("service", "klaim rfid_verify_sessions (status open) sesudah validasi scope/status, sebelum print job & journey ditulis; mark_failed bila gagal; finish_set status completed", "rfid_print_service.complete_verify"),
    ("rfid.py", "POST /rfid/cycle-count/{session_id}/complete"): ("service", "klaim rfid_verify_sessions (status open) sesudah validasi; insert rfid_cycle_counts lalu finish_set sesi → klik ganda/balapan hanya satu CC", "cycle_count_service.complete"),
    ("transfers.py", "POST /transfers/inter-company"): ("none", "ditutup PK-30 — selalu 410 tanpa menulis (sesudah pemeriksaan izin; isi permintaan diabaikan, roll tidak direservasi)"),
    ("rfid.py", "POST /rfid/roll-scans"): ("service", "POST: roll_scans append-only (id baru per pindai) + inventory_rolls.last_scan CAS 'hanya maju' (last_scan.at < at) — idempoten via Idempotency-Key; tak ada saldo/status dokumen"),
    ("bank_reconciliation.py", "POST /bank-reconciliation/lines/{line_id}/book-charge"): ("service", "klaim bank_statement_lines (status bukan matched/holding) sesudah validasi jenis/nominal, sebelum kas+jurnal+link; mark_failed bila gagal; finish_set", "bank_recon_service.book_charge"),
    ("bank_reconciliation.py", "POST /bank-reconciliation/lines/{line_id}/holding"): ("service", "POST: klaim bank_statement_lines (bukan matched/holding) sesudah validasi arah/status, sebelum kas titipan+jurnal; finish_set status holding", "bank_recon_service.to_holding"),
    ("bank_reconciliation.py", "POST /bank-reconciliation/lines/{line_id}/holding/allocate"): ("service", "klaim bank_statement_lines (status holding) sesudah validasi Σ alokasi, AR+jurnal per alokasi di dalam klaim; mark_failed bila gagal; finish_set holding_remaining", "bank_recon_service.allocate_holding"),
    ("bank_reconciliation.py", "POST /bank-reconciliation/lines/{line_id}/holding/cancel"): ("service", "klaim bank_statement_lines (status holding) sesudah validasi, sebelum kas void + jurnal balik; finish_set status unmatched", "bank_recon_service.cancel_holding"),
    ("access_review.py", "POST /access/role-reality/{user_id}/apply"): ("service", "dua tulisan idempoten: users.role (update_user) + sesi dicabut (delete_many); pengulangan → 400 'peran sudah sama'; tidak ada saldo/stok"),
    ("entities.py", "POST /entities"): ("service", "POST: id badan usaha baru per permintaan; insert lalu seed COA (idempoten) + upsert system_settings; sinkron partner grup best-effort — tak ada saldo bersama, aman diulang"),
    ("entities.py", "POST /entities/{entity_id}/archive"): ("service_cas", "find_one_and_update business_entities berprasyarat status ≠ archived → 409 STATE_CHANGED; sesi pengguna dicabut idempoten (delete_many)", "entity_lifecycle_service.archive_entity"),
    ("entities.py", "DELETE /entities/{entity_id}"): ("service_cas", "DELETE (=archive): CAS status ≠ archived di lifecycle.archive_entity → 409 bila kalah", "entity_lifecycle_service.archive_entity"),
    # ── KP-T6 (14 Nov 2026) ──
    ("pdf.py", "POST /branding/{entity_id}/identity"): ("service", "validasi Profil PT (400) SEBELUM menulis; klaim = update_one document_branding berprasyarat identity_resolved_at kosong (kalah → 409, tanpa tulisan lain); baru sesudah menang $set isian Profil PT (idempoten, nilai sama bila diulang) + jejak append-only — tak ada saldo/stok"),
    ("config.py", "POST /impact-apply"): ("service", "klaim products sesudah validasi alasan/cakupan (ImpactError), master + SO ditulis ulang di dalam klaim; mark_failed bila gagal; release di finally", "config_impact_service.apply"),
    ("auth.py", "POST /auth/login"): ("service", "login_attempts + sessions + users(last_login): tulisan independen, tidak ada saldo/stok — aman diulang"),
    ("categories.py", "PATCH /product-categories/{category_id}"): ("claim", "PATCH: klaim product_categories sesudah validasi nama/duplikat, sebelum products.update_many (rename kaskade); mark_failed bila gagal; finish_set"),
    ("special_orders.py", "POST /special-orders/{order_id}/convert-to-so"): ("claim", "klaim special_orders (linked_sales_order_id kosong) sesudah validasi status/SKU, sebelum SO lahir; release bila create_order gagal; finish_set tautan SO"),
    ("wms.py", "POST /wms/tasks/outbound-from-order/{order_id}"): ("claim", "klaim sales_orders sesudah validasi status, sebelum tugas outbound lahir (cek 'belum ada tugas' + insert tak lagi bisa balapan); release di finally"),
    # ── PREP-B (8 Nov 2026) — pendaftaran awal gedung (opname awal RFID) ──
    ("initial_registration.py", "POST /registration/sessions/{sid}/approve"): ("service", "klaim cycle_count_sessions (status pending_approval) sebelum roll baru dibuat / roll lama dipakai ulang atau dihapus, tag ditautkan & jurnal per produk; langkah idempoten (id roll deterministik, catatan operasi bertahap, jurnal per source_id); gagal → release agar pengulangan melanjutkan; finish_set", "initial_registration_approve.approve"),
    ("initial_registration.py", "POST /registration/sessions/{sid}/reject"): ("service_cas", "find_one_and_update cycle_count_sessions berprasyarat status terbuka & tanpa saga_lock → rejected + pembekuan dilepas; baris draf dibatalkan sesudahnya (update_many idempoten, tanpa saldo)", "initial_registration_service.reject"),
    # ── Sesi 18 — ratchet ke 0 ──
    ("esign.py", "POST /request"): ("service", "POST: hanya esign_requests yang ditulis (id baru per permintaan); sample_requests/wms_tasks cuma DIBACA untuk hash dokumen — tak ada saldo/status bersama"),
    ("esign.py", "POST /verify"): ("service", "klaim esign_requests (status pending) sesudah OTP tervalidasi, sebelum document_signatures ditulis; mark_failed bila hash gagal; finish_set status verified", "esign_service.verify_and_sign"),
    ("fixed_assets.py", "POST /fixed-assets/run-depreciation"): ("service_cas", "per aset: find_one_and_update berprasyarat status + depreciation_periods $ne periode ($addToSet) — kalah → dilewati; entri+JE hanya oleh pemenang", "fixed_asset_service.run_depreciation"),
    ("hr_payroll.py", "POST /hr/payroll/runs"): ("service", "POST: run baru per permintaan; balapan run kedua untuk entitas+periode sama → run milik permintaan ini dihapus & run lain dikembalikan; slip gagal → rollback_run (kompensasi saga)"),
    ("input_tax.py", "POST /input-tax-invoices"): ("claim", "POST: klaim vendor_bills (input_faktur_status bukan aktif) sesudah validasi NSFP/dedupe, sebelum tax_invoices_in lahir; release bila insert gagal; finish_set penanda bill"),
    ("input_tax.py", "POST /input-tax-invoices/{fpm_id}/cancel"): ("claim", "klaim tax_invoices_in (status != cancelled) sesudah validasi alasan, sebelum bill dilepas; finish_set status cancelled"),
    ("inventory.py", "POST /inventory/putaway"): ("service", "putaway_roll: roll.bin_id di-set idempoten + inventory_movements putaway qty 0 (jejak, bukan saldo) — aman diulang, tak butuh kunci"),
    ("landed_cost.py", "POST /landed-costs/{voucher_id}/approve"): ("claim", "klaim landed_cost_vouchers (status pending) sesudah validasi peran/roll target, sebelum HPP roll ditulis; mark_failed bila alokasi gagal; finish_set applied"),
    ("landed_cost.py", "POST /landed-costs/{voucher_id}/pay"): ("claim", "klaim landed_cost_vouchers (status applied) sesudah validasi sisa, sebelum kas+GL lahir; mark_failed bila kas gagal; finish_set + $inc amount_paid"),
    ("makloon_orders.py", "POST /makloon-orders/{mko_id}/receive"): ("service", "klaim makloon_orders sesudah validasi qty/lot, sebelum roll input dikonsumsi/tagihan jasa/lot output; replace_one tanpa saga_lock + release", "makloon_order_service.receive_step"),
    ("makloon_orders.py", "POST /makloon-orders/{mko_id}/record-service"): ("service", "klaim makloon_orders sesudah validasi biaya, sebelum vendor_bills jasa lahir; replace_one tanpa saga_lock + release", "makloon_order_service.record_service_step"),
    ("outbound_picking.py", "POST /outbound/loading-check/{session_id}/complete"): ("service", "klaim rfid_verify_sessions (status open) sesudah validasi jenis/scope, sebelum sales_orders.loading_check ditulis; finish_set completed", "loading_check_service.complete"),
    ("product_templates.py", "DELETE /product-templates/{template_id}"): ("service", "DELETE: klaim product_templates sebelum varian dilepas (update_many); release bila detach gagal; delete_one mencabut dokumen beserta kuncinya", "product_template_service.delete_template"),
    ("rfq.py", "POST /rfqs/{rfq_id}/award"): ("service", "klaim rfqs (status open) sesudah validasi mode/harga, sebelum PO lahir; release bila belum ada PO, mark_failed bila PO parsial; finish_set awarded", "rfq_service.award_rfq"),
    ("rnd.py", "POST /rnd/samples/{sample_id}/issue-material"): ("service_cas", "find_one_and_update inventory_rolls berprasyarat status + length_remaining sama seperti saat dibaca → kalah = RndError; JE gagal → mutasi & roll dipulihkan (kompensasi pra-eksisting)", "rnd_sample_service.issue_material"),
    ("sales_orders_extra.py", "POST /sales-orders/{order_id}/mark-delivered"): ("cas", "_transition CAS status shipped → done (409 bila kalah); deliver_order_rolls idempoten (set status delivered pada roll order)"),
    ("sales_returns.py", "POST /sales-returns/{return_id}/create-purchase-return"): ("service", "klaim sales_returns (linked_purchase_return_id kosong) sesudah validasi roll/supplier, sebelum purchase_returns lahir; release bila gagal; finish_set tautan", "purchase_return_service.create_from_sales_return"),
    ("so_approvals.py", "POST /sales-orders/{order_id}/request-credit-approval"): ("claim", "klaim sales_orders sesudah validasi status/duplikat pending, sebelum credit_overrides lahir; finish_set credit_hold"),
    ("special_orders.py", "POST /special-orders/{order_id}/create-pr"): ("claim", "klaim special_orders (linked_pr_id kosong) sesudah validasi status/gudang, sebelum PR lahir; release bila create_requisition gagal; finish_set tautan PR"),
    ("special_orders.py", "POST /special-orders/{order_id}/create-sku"): ("service", "klaim special_orders (linked_product_id kosong) sesudah validasi, sebelum products lahir; release bila insert gagal; finish_set tautan SKU", "special_order_service.create_sku_from_special_order"),
    ("users.py", "POST /users"): ("service", "POST: users baru per permintaan; hr_employees.user_id gagal → akun yang baru lahir dihapus (kompensasi saga); tak ada saldo bersama"),
    ("users.py", "PATCH /users/{user_id}"): ("service", "PATCH: users $set + hr_employees.user_id (idempoten, tautan satu arah) + sesi dicabut (delete_many) — tulisan independen tanpa saldo/stok, aman diulang"),
    ("warehouse_sites.py", "POST /warehouse-sites/seed-blueprint"): ("service", "POST seed: warehouses/warehouse_sites di-upsert per kode (idempoten) — pengulangan tidak menggandakan; tak ada saldo"),
    # ── FIX-6 (keputusan pemilik 10 Nov 2026) — penanda "minta inspeksi" saat penerimaan ─────────────
    ("inbound_receiving_extra.py", "POST /inbound/tasks/{task_id}/inspection-request"): ("cas", "FIX-6: find_one_and_update wms_tasks berprasyarat status ∈ (belum lepas karantina) → 409 bila kalah; penanda yang sama ditempel ke roll tugas (update_many idempoten, nilai sama bila diulang) + audit append-only; tanpa saldo/stok"),
    # ── PREP-A (K-OPN-06, 9 Nov 2026) — lembar perbaikan master produk ─────────────────────
    ("master_governance.py", "POST /master-governance/cleanup/apply"): ("service", "rencana batch durable (status planned) → klaim master_cleanup_batches sesudah validasi+tanda tangan pratinjau; per baris CAS produk (status/updated_at/belum digantikan seperti dibaca), produk baru insert ber-SKU unik + kompensasi; finish_set status applied", "master_cleanup_service.apply_cleanup"),
    ("master_governance.py", "POST /master-governance/cleanup/batches/{batch_id}/rollback"): ("service", "klaim master_cleanup_batches (status applied*) sesudah validasi alasan/peran; tiap baris dibalik dengan CAS last_cleanup_batch + nilai sesudah; produk yatim dipindai dari penanda batch; finish_set rolled_back", "master_cleanup_service.rollback_cleanup"),
    # ── PK-33 (14 Nov 2026) — penggolongan endpoint yang muncul sesudah pencacah & kunci diperbaiki ─────────────────
    # Golongan 1 — sudah berklaim/CAS (dicatat, kode tidak diubah).
    ("cycle_count.py", "POST /cycle-count/sessions/{session_id}/roll-finalize"): ("claim", "PK-33: klaim cycle_count_sessions (status open) sesudah validasi izin/cakupan PT/spesifikasi roll/alasan/periode buku, sebelum penyesuaian roll, hapus roll hilang & roll temuan; mark_failed bila gagal; release bila ada roll yang harus dihitung ulang; finish_set status approved*"),
    ("sales_return_exceptions.py", "POST /sales-returns/{return_id}/replacement-order"): ("claim", "PK-33: klaim sales_returns berprasyarat replacement_order_id kosong sebelum harga khusus + SO pengganti lahir; release di finally (galat 400 di dalam try ikut melepas); pemanggil kedua kalah klaim atau prasyarat → 409"),
    ("sales_returns.py", "POST /sales-returns/{return_id}/settle"): ("service", "PK-33: klaim sales_returns berprasyarat status seperti dibaca di settle_return sesudah assert_transition + pemeriksaan rekening, sebelum stok/nota kredit/kas; finish_set; tulisan router sesudahnya ($set decision/return_type nilai sama) idempoten — jalur nota kredit milik PK-32", "return_service.settle_return"),
    ("vendor_bills.py", "POST /vendor-bills/{bill_id}/payments/{payment_id}/void"): ("cas", "PK-33: find_one_and_update vendor_bills berprasyarat $elemMatch pembayaran ini belum voided (kalah → 409) SEBELUM kas di-void + jurnal kas dibalik; sync_po_billing menghitung ulang PO dari tagihan (idempoten)"),
    ("goods_receipts.py", "POST /goods-receipts/{grn_id}/start-count"): ("service_cas", "PK-33: CAS goods_receipts status review + versi (`cas(grn, [review], expected_version)`) → 409; tugas PO diambil find_one_and_update berprasyarat status hidup + grn_active_id kosong/sama, kalah → tugas dilepas + GRN kembali review + 409", "goods_receipt_service.start_count"),
    ("cutting.py", "POST /tasks/{task_id}/receive"): ("service_cas", "PK-33: find_one_and_update wms_tasks berprasyarat status bukan terminal + cutting_handoff.received_at kosong (pemenang tunggal); timeline SO $push & alokasi $set hanya oleh pemenang; transfer lintas gedung dipakai ulang bila sudah ada (CAS transfer_ref roll)", "cutting_service.receive"),
    ("purchase_orders.py", "POST /purchase-orders/{po_id}/approve"): ("cas", "PK-33: find_one_and_update(_cas) — filter bernama berprasyarat status waiting_approval + tingkat berjalan + versi → 409 bila kalah; tugas penerimaan hanya oleh pemenang (dedupe per produk), close_amendment_tasks CAS per tugas, notifikasi idempoten"),
    ("purchase_orders.py", "POST /purchase-orders/{po_id}/amend"): ("service_cas", "PK-33: update_one(_cas) berprasyarat status + updated_at + tingkat seperti dibaca, modified_count 0 → 409 SEBELUM tugas 0-diterima dihapus; router sesudahnya: close_amendment_tasks CAS per tugas, tugas penerimaan dedupe per produk", "po_amendment_service.amend_po"),
    ("client_dataset.py", "POST /batches/{batch_id}/rollback"): ("service_cas", "PK-33: find_one_and_update client_dataset_imports berprasyarat status committed|failed → rolling_back (pemenang tunggal) sebelum templat/produk/item pemasok dipulihkan ke potret before; pembatalan berurutan dari impor terakhir dicek lebih dulu", "client_dataset_service.rollback"),
    ("makloon_orders.py", "POST /makloon-orders/{mko_id}/steps/{seq}/service-invoice"): ("service_cas", "MP-T4b: update_one vendor_bills berprasyarat status awaiting_invoice → posted, modified_count 0 → 409 (pemenang tunggal) SEBELUM langkah SPK ditandai cocok ($set idempoten) dan jurnal faktur lewat post_durable (idempoten per tagihan)", "makloon_ap_service.match_invoice"),
    ("makloon_orders.py", "POST /makloon-orders/{mko_id}/steps/{seq}/partial-receipts/{grn_id}/cancel"): ("service_cas", "PK-33: update_one makloon_orders berprasyarat tanpa saga_lock + $elemMatch langkah issued berisi kiriman ini belum posted, modified_count 0 → 409; GRN dibatalkan update_one berprasyarat status closed (ulangan = no-op)", "makloon_order_service.cancel_partial_receipt"),
    ("customers.py", "POST /customers/{customer_id}/merge"): ("service_cas", "PK-33: kunci gabung = update_one customers sumber berprasyarat status != merged + merge_lock kosong, modified_count 0 → 409, SEBELUM dokumen dipindah (update_many customer_id, $set nilai sama bila diulang); tulisan akhir status merged + $unset merge_lock", "customer_merge_service.merge"),
    ("hr_payroll.py", "POST /hr/payroll/runs/{run_id}/recalculate"): ("service_cas", "PK-33: find_one_and_update hr_payroll_runs berprasyarat status draft + recalc_claim kosong (pemenang tunggal) sebelum slip diganti di tempat (id & nomor tetap); recalc_claim dicabut di finally", "hr_payroll_service.recalculate_run"),
    ("master_governance.py", "POST /master-governance/batches/{batch_id}/rollback"): ("service_cas", "PK-33: find_one_and_update master_governance_batches berprasyarat status applied|applying → rolling_back (pemenang tunggal); tiap produk dibalik CAS field == after + last_governance_batch batch ini", "master_governance_service.rollback_batch"),
    ("transfers.py", "POST /transfers/{transfer_id}/exceptions/{exc_id}/resolve"): ("service_cas", "PK-33: roll dikembalikan lewat update_one(held_cas(roll)) — status/gudang/komitmen seperti dibaca; mutasi + hitung ulang saldo HANYA bila matched; exception $set resolved (nilai sama), status transfer dihitung ulang", "transfer_receipt_service.resolve"),
    # Golongan 2 — tulisan aman diulang & aman berbalapan (alasan MENGAPA per baris).
    ("inspections.py", "POST /inspections/{ins_id}/lines/{line_id}/mdq-cut"): ("none", "PK-33: kunci idempotensi mdq_cuts `_id` = inspeksi:baris (sisip-bila-belum-ada; kembar → 409, posted → jawaban ulang tanpa tulis); pengurangan roll update_one berprasyarat status + panjang bebas ≥ qty (kalah → catatan pending dihapus + 409); jurnal hapus-buku per source_id mdq:<kunci>"),
    ("sales_returns.py", "POST /sales-returns"): ("none", "PK-33: id retur baru per permintaan; kunci per SO = insert return_create_locks `_id` = order_id (kembar → 400 'sedang disimpan') membungkus cek batas retur + pembuatan, dilepas di finally — dua retur bersamaan untuk SO yang sama tidak bisa sama-sama lolos cek batas"),
    ("inventory.py", "POST /inventory/rolls/{roll_id}/fix-location"): ("none", "PK-33: satu roll — bin ditulis lewat penulis bin tunggal putaway_roll/place_roll (CAS bin & gudang seperti dibaca, qty tidak berubah) atau dikosongkan ($set nilai sama); location_corrections = jejak tambah-saja; tidak ada saldo/stok/status dokumen"),
    ("design_gallery.py", "PUT /design-gallery/{gallery_id}"): ("none", "PK-33: $set field master satu dokumen design_gallery + timeline tambah-saja; sync_products menulis ulang turunan desain di SKU dari dokumen desain terbaru (update_many $set nilai yang sama bila diulang) — tidak ada saldo/stok/status bisnis"),
    ("access_roles.py", "PATCH /roles/{rid}"): ("none", "PK-33: tulisan pengaturan peran ($set level/izin/sifat/label ke custom_roles + permission_settings) — mengulang PATCH yang sama menulis nilai yang sama; tidak ada saldo/stok/dokumen bisnis. Sisa di luar INV-ATOMIC-01: matriks disimpan utuh, dua PATCH peran berbeda bersamaan bisa saling menimpa"),
    ("access_roles.py", "DELETE /roles/{rid}"): ("none", "PK-33: hapus peran kustom + $unset pengaturan per peran (idempoten; ulangan → 400 karena peran sudah tidak ada); ditolak 409 selama masih ada akun berperan itu; tidak ada saldo/stok/dokumen bisnis"),
    ("warehouses.py", "PUT /warehouses/{warehouse_id}/structure"): ("none", "PK-33: $set zones satu dokumen gudang + location_migrations jejak tambah-saja (lahir hanya bila bin berisi berubah; ulangan isi sama → tanpa perubahan → tanpa jejak baru); bin berisi roll/tugas tidak bisa dihapus (409); tidak ada saldo/stok"),
    ("warehouses.py", "PATCH /warehouses/{warehouse_id}"): ("none", "PK-33: $set field master gudang (find_one_and_update satu dokumen); zona lewat jalur struktur berpenjaga save_warehouse_structure (jejak migrasi tambah-saja); ulangan menulis nilai sama; tidak ada saldo/stok"),
    ("handheld.py", "POST /tag-writes/{write_id}/confirm"): ("none", "PK-33 · H7 (RFID, kode tidak diubah): idempoten per client_request_id lewat `once(...)`; niat tulis confirmed → jawaban ulang tanpa tulis; tag baru lewat rfid_service.encode_tag (CAS rfid_tag_id kosong, kalah → 409 + tag lama dipulihkan); niat ditutup update_one berprasyarat status pending; tanpa saldo/stok"),
    ("outbound_picking.py", "POST /outbound/so/{order_id}/loading-check/simulate-tags"): ("none", "PK-33 · H7 (RFID, kode tidak diubah): hanya saat mode simulasi RFID menyala (selain itu 409); tiap roll SO tanpa tag hidup di-encode lewat rfid_service.encode_tag (CAS rfid_tag_id kosong → yang kalah 409); ulangan melewati roll yang sudah bertag hidup; tanpa saldo/stok/status dokumen"),
    ("master_governance.py", "POST /master-governance/batches"): ("none", "PK-33: batch baru (id acak) per permintaan dengan rencana durable dulu; tiap produk diubah update_one CAS field == nilai pratinjau (kalah → tidak masuk changes batch itu), jadi dua eksekusi bersamaan tidak mengubah satu produk dua kali; tidak ada saldo/stok"),
    ("special_orders.py", "POST /special-orders/{order_id}/fulfillment/{item_key}/route"): ("none", "PK-33: jalur sama → jawaban tanpa tulis; update_one special_orders berprasyarat versi jalur item (matched 0 → 409) SEBELUM PR lama dibatalkan, jadi hanya pemenang yang membatalkan PR (cancel_requisition berpenjaga status; $set source_item_key nilai sama)"),
    # Golongan 4 — klaim ditambahkan PK-33 (uji: tests_mem/test_PK33_atomisitas.py U7/U9; lapis A tests/test_bp_PK33_klaim_bersamaan.py U8).
    ("sales_returns.py", "POST /sales-returns/{return_id}/roll-settlement/back-shipment"): ("service", "PK-33 (golongan 4): klaim sales_returns berprasyarat roll yang dikirim masih back_pending, sesudah validasi, sebelum nomor + surat jalan lahir; mark_failed bila gagal; finish_set back_pending False + nomor surat jalan", "return_roll_settlement_service.back_shipment"),
    ("hr_leave.py", "POST /hr/leave-requests"): ("service", "PK-33 (golongan 4): klaim hr_employees sesudah validasi isian, sebelum cek tabrakan tanggal + reservasi saldo (CAS $inc pending) + sisip pengajuan; kunci milik pemanggil dilepas di finally (semua tulisan bisa dihitung ulang dari pengajuan)", "hr_leave_service.submit_leave"),
    ("hr_leave.py", "POST /hr/leave-requests/me"): ("service", "PK-33 (golongan 4): layanan sama dengan pengajuan oleh HR — klaim hr_employees sesudah validasi isian, sebelum cek tabrakan + reservasi saldo + sisip; dilepas di finally", "hr_leave_service.submit_leave"),
    # LB-T4 — Lapor Bayar: keputusan Finance atas laporan (uji: tests_mem/test_LB4_putus.py, terima ganda/bersamaan).
    ("payment_reports.py", "POST /payment-reports/{report_id}/terima"): ("service_cas", "LB-T4: find_one_and_update payment_reports berprasyarat status menunggu (atau memproses dengan klaim basi) → memproses ber-token (kalah → 409) SEBELUM create_receipt; kwitansi dicari dulu lewat rujukan balik payment_report_id (ada → dipakai, tidak menerbitkan kedua); gagal → kembali menunggu bersyarat token; selesai → diterima bersyarat token", "payment_report_service._klaim"),
    ("payment_reports.py", "POST /payment-reports/{report_id}/tolak"): ("service_cas", "LB-T4: find_one_and_update payment_reports berprasyarat status menunggu → ditolak (kalah → 409); tanpa uang, hanya notifikasi + audit sesudahnya", "payment_report_service.tolak"),
}

MECHS = {"claim", "cas", "service", "service_cas", "compensate", "none", "unit"}
RE_KEY = re.compile(r"^(POST|PUT|PATCH|DELETE) /")

# `family_lock(` = context manager di product_variant_service yang MEMBUNGKUS
# atomic_claim.claim() + release() (klaim per keluarga produk). Diakui sebagai klaim
# + pencabut kunci yang sah — bukan allowlist per fungsi.
RE_CLAIM = re.compile(r"atomic_claim|_saga\.claim\(|family_lock\(")
# PK-33 — pencabut kunci lewat alias modul (`from services import atomic_claim as saga` → `saga.release(`) dan nama
# kanoniknya (`atomic_claim.release(`) juga sah; dulu hanya `_saga.release(` yang dikenali.
# FIX-10 — `claimed=True` (`cycle_count_state.transition`) & `_pst.finish_claimed(` (`putaway_state`) = tulisan akhir
# klaim yang mensyaratkan kunci masih dipegang lalu mencabutnya (setara finish_set).
RE_FINISH = re.compile(r"finish_set\(|\$unset\"?\s*:\s*\{\s*\"saga_lock\"|so_transition|_transition\(|\b_?saga\.release\(|atomic_claim\.release\(|family_lock\(|claimed=True|_pst\.finish_claimed\(")
# FIX-3a — `_its.transition(` = `services/inbound_task_state.transition` (CAS: filter id + status asal ∈ daftar-izin).
# FIX-3b — `_ots.transition(` = `services/outbound_task_state.transition` (CAS daftar-izin tugas ambil keluar).
# FIX-10 — `_rs.transition(` (`roll_state`: CAS status asal roll + daftar-izin), `ccs.transition(` (`cycle_count_state`),
# `_ist.cas_filter(` (`inspection_state`) = CAS status asal ∈ daftar-izin di filter tulis.
# PK-33 — pola CAS sah yang dulu tak dikenali (masing-masing berpasangan uji-diri hijau/merah):
#   · `$elemMatch` berprasyarat pada unsur larik di filter tulis (`{"payments": {"$elemMatch": {"id": p, "voided": {"$ne": True}}}}`)
#   · prasyarat status yang DITERUSKAN ke penulis tunggal (`place_roll(…, cas={"status": "receiving"})` → filter update_one)
#   · hapus bersyarat status (`delete_one({"id": i, "status": "receiving"})` → deleted_count 0 = kalah)
#   · filter bernama berisi status (`_cas = {"id": …, "status": …}` → `find_one_and_update(_cas, …)`, atau
#     `update_one(_cas, …)` yang hasilnya diperiksa `modified_count`/`matched_count` ≤ 3 baris)
#   · `update_one({… "status": …}, …)` yang hasilnya diperiksa `modified_count`/`matched_count` ≤ 3 baris
#   · `update_one(held_cas(roll), …)` — `roll_service.held_cas` = status + gudang + komitmen roll seperti dibaca
RE_CAS = re.compile(r"find_one_and_update\(\s*\{[^}]*\"(status|escalation\.status|rfid_tag_id)\"|_transition\(|_its\.transition\(|_ots\.transition\(|find_one_and_update\(\s*\n?\s*\{\"id\": bill_id, \"status\""
                    r"|(find_one_and_update|update_one)\([^)]*?\"\$elemMatch\":\s*\{[^}]*(\"status\"|\"\$(ne|nin|in|eq)\")"
                    r"|\bcas=\{\s*\"status\""
                    r"|delete_one\(\s*\{[^}]*\"status\""
                    r"|(?P<cv1>\b\w+)\s*=\s*\{[^}]*\"status\"[\s\S]*?find_one_and_update\(\s*(?P=cv1)\s*,"
                    r"|(?P<cv2>\b\w+)\s*=\s*\{[^}]*\"status\"[\s\S]*?update_one\(\s*(?P=cv2)\s*,[^\n]*\n(?:[^\n]*\n){0,2}?[^\n]*(modified|matched)_count"
                    r"|update_one\(\s*\{[^}]*\"status\"[^\n]*\n(?:[^\n]*\n){0,2}?[^\n]*(modified|matched)_count"
                    r"|\bupdate_one\(\s*held_cas\("
                    r"|_rs\.transition\(|\bccs\.transition\(|_ist\.cas_filter\(")
RE_COMP = re.compile(r"except[^\n]*:\s*\n\s*await (release_|_release|rollback|compensate)")
# Validasi 400/404/422 SESUDAH klaim meninggalkan saga_lock → percobaan ulang yang benar ditolak 409
# (bukti: inbound complete × pagar lot mode block, sesi 4). Klaim wajib SESUDAH semua validasi.
RE_LATE_VALIDATION = re.compile(r"raise HTTPException\(\s*status_code=4(00|04|22)")
RE_RELEASE_BEFORE = re.compile(r"await _?saga\.release\(|await atomic_claim\.release\(|await _?saga\.mark_failed\(|await atomic_claim\.mark_failed\(")
# PK-33 — mekanisme `unit`: "<ID>: <alasan>"; ID dari INDEKS_UNIT.md, status dari STATUS.md.
RE_UNIT_REASON = re.compile(r"^\s*([A-Z]{2}-[A-Z0-9]+)\s*:\s*(.+)$", re.S)
RE_UNIT_ID = re.compile(r"^[A-Z]{2}-[A-Z0-9]+$")
UNIT_DONE = {"selesai", "tervalidasi"}
BLUEPRINT = ROOT / "docs" / "blueprint"


def validation_after_claim(src: str) -> str | None:
    """Baris pertama `raise HTTPException(status_code=400/404/422)` sesudah `_saga.claim(`; None bila bersih.
    Raise yang didahului `release(` atau `mark_failed(` (≤3 baris sebelumnya) dianggap sudah menangani kunci
    (dilepas, atau sengaja dibiarkan dengan alasan tercatat karena tulisan turunan sudah terjadi) → bukan pelanggaran."""
    lines = src.splitlines()
    # PK-33 — `saga.claim(` (alias tanpa garis bawah) juga klaim; raise di dalam `try:` yang `finally:`-nya melepas
    # kunci (≤4 baris sesudah raise) juga sudah menangani kunci.
    idx = next((i for i, l in enumerate(lines) if "saga.claim(" in l or "atomic_claim.claim(" in l), None)
    if idx is None:
        return None
    for j in range(idx + 1, len(lines)):
        l = lines[j]
        if RE_LATE_VALIDATION.search(l):
            if any(RE_RELEASE_BEFORE.search(p) for p in lines[max(idx + 1, j - 3):j]):
                continue
            fin = next((k for k in range(j + 1, min(j + 5, len(lines))) if lines[k].strip() == "finally:"), None)
            if fin is not None and any(RE_RELEASE_BEFORE.search(p) for p in lines[fin + 1:fin + 3]):
                continue
            return l.strip()
    return None


def service_function_source(ref: str) -> str | None:
    """'modul.fungsi' → sumber fungsi di backend/services/modul.py (None bila tak ada)."""
    mod, _, fn = ref.rpartition(".")
    f = BACKEND / "services" / f"{mod}.py"
    if not f.exists():
        return None
    src = f.read_text(errors="ignore")
    tree = ast.parse(src)
    lines = src.splitlines()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn:
            return "\n".join(lines[n.lineno - 1:n.end_lineno])
    return None


@lru_cache(maxsize=1)
def _router_index() -> tuple[dict, dict]:
    """(sumber endpoint, sumber pembantu modul yang sama) berkunci (berkas router, "METODE /path")."""
    out: dict[tuple[str, str], str] = {}
    helpers: dict[tuple[str, str], list[str]] = {}
    for f in sorted((BACKEND / "routers").glob("*.py"), key=lambda p: p.name):
        src = f.read_text(errors="ignore")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        lines = src.splitlines()
        fns = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for n in fns.values():
            keys = [k for k in inv.route_keys(n) if not k.endswith(" ?")]
            if not keys:
                continue
            body = "\n".join(lines[n.lineno - 1:n.end_lineno])
            # PK-33 B.3 — pembantu tingkat modul di berkas router yang sama yang dipanggil endpoint (satu tingkat;
            # pembantu yang juga endpoint tidak dihitung).
            called = sorted({c.func.id for c in ast.walk(n) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                             and c.func.id in fns and c.func.id != n.name and not inv.route_keys(fns[c.func.id])})
            hsrc = ["\n".join(lines[fns[h].lineno - 1:fns[h].end_lineno]) for h in called]
            for k in keys:
                out[(f.name, k)] = body
                helpers[(f.name, k)] = hsrc
    return out, helpers


def endpoint_sources() -> dict[tuple[str, str], str]:
    """{(router file, "METODE /path"): sumber fungsi} untuk semua endpoint tulis di backend/routers."""
    return dict(_router_index()[0])


def helper_sources() -> dict[tuple[str, str], list[str]]:
    """{(router file, "METODE /path"): [sumber pembantu modul yang sama yang dipanggil endpoint]}."""
    return dict(_router_index()[1])


def unit_statuses(indeks: str | None = None, status: str | None = None) -> dict[str, str | None]:
    """{ID unit: status} — ID dari INDEKS_UNIT.md, status dari STATUS.md (None bila tak tercatat di papan)."""
    if indeks is None:
        indeks = (BLUEPRINT / "INDEKS_UNIT.md").read_text(errors="ignore")
    if status is None:
        status = (BLUEPRINT / "STATUS.md").read_text(errors="ignore")

    def rows(text):
        for line in text.splitlines():
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > 3 and RE_UNIT_ID.match(cells[2]):
                yield cells
    st = {c[2]: c[5] for c in rows(status) if len(c) > 5}
    return {c[2]: st.get(c[2]) for c in rows(indeks)}


def _tanpa_aman(reason: str) -> str:
    """Alasan tanpa kata 'aman' (alasan `none` yang hanya berbunyi "aman" tidak menjelaskan MENGAPA)."""
    return re.sub(r"\baman\b", "", reason, flags=re.I).strip(" .,;:-—")


def unreviewed_rows(reviewed=REVIEWED, rows: list | None = None) -> list[tuple[str, str]]:
    """Endpoint ≥2 koleksi substantif (dari inventaris) yang belum masuk REVIEWED (kunci sama persis)."""
    rows = inv.collect_rows() if rows is None else rows
    out = []
    for fn, _ln, path, _direct, _via, allc in rows:
        if len([c for c in allc if c not in inv.LOG_ONLY]) < 2:
            continue
        if (fn, path) not in reviewed:
            out.append((fn, path))
    return out


def check(sources: dict[tuple[str, str], str], reviewed=REVIEWED, unreviewed: list | None = None,
          baseline: int = BASELINE_UNREVIEWED, helpers: dict | None = None, units: dict | None = None) -> Guard:
    g = Guard("INV-ATOMIC-01", "endpoint tulis multi-koleksi memakai klaim atomik / CAS (saga, tanpa transaksi)")
    for (rf, key), entry in sorted(reviewed.items()):
        mech, reason = entry[0], entry[1]
        svc_ref = entry[2] if len(entry) > 2 else None
        g.bump()
        if not RE_KEY.match(key):
            g.add(f"REVIEWED {rf} '{key}': kunci wajib berbentuk 'METODE /path persis' (PK-33).")
            continue
        if mech not in MECHS:
            g.add(f"REVIEWED {rf} {key}: mekanisme '{mech}' tidak dikenal ({', '.join(sorted(MECHS))}).")
            continue
        if (rf, key) not in sources:
            g.add(f"REVIEWED {rf} {key}: endpoint tidak lagi ada di kode — hapus entrinya (ratchet).")
            continue
        src = sources[(rf, key)]
        pieces = [src] + list((helpers or {}).get((rf, key), []))
        allsrc = "\n".join(pieces)
        if len(reason.strip()) < 20:
            g.add(f"{rf} {key}: alasan REVIEWED terlalu pendek (<20 huruf).")
        if mech == "none" and len(_tanpa_aman(reason)) < 20:
            g.add(f"{rf} {key}: alasan 'none' harus menyebut MENGAPA pengulangan & balapan aman (bukan sekadar 'aman').")
        if mech == "unit":
            m = RE_UNIT_REASON.match(reason)
            st = unit_statuses() if units is None else units
            if not m:
                g.add(f"{rf} {key}: mekanisme 'unit' wajib beralasan '<ID unit>: <alasan>'.")
            elif len(m.group(2).strip()) < 20:
                g.add(f"{rf} {key}: alasan 'unit' {m.group(1)} terlalu pendek (<20 huruf sesudah ID).")
            elif m.group(1) not in st:
                g.add(f"{rf} {key}: unit '{m.group(1)}' tidak dikenal di docs/blueprint/INDEKS_UNIT.md.")
            elif (st[m.group(1)] or "").strip().lower() in UNIT_DONE or st[m.group(1)] is None:
                g.add(f"{rf} {key}: unit {m.group(1)} sudah {st[m.group(1)] or 'tidak tercatat di STATUS.md'} — "
                      "ganti mekanisme 'unit' dengan mekanisme nyata (claim/cas/service/none).")
        if mech == "claim" and not RE_CLAIM.search(allsrc):
            g.add(f"backend/routers/{rf} {key}: dicatat 'claim' tetapi tidak memanggil atomic_claim.claim(). Pasang klaim atau ubah mekanisme.")
        if mech == "claim" and not RE_FINISH.search(allsrc):
            g.add(f"backend/routers/{rf} {key}: klaim tanpa pencabut kunci (finish_set / $unset saga_lock / so_transition / release).")
        if mech == "claim":
            for piece in pieces:
                if (late := validation_after_claim(piece)):
                    g.add(f"backend/routers/{rf} {key}: validasi 4xx SESUDAH klaim (`{late[:70]}`) — kunci tertinggal; pindahkan ke atas klaim atau release() dulu.")
                    break
        if mech == "cas" and not RE_CAS.search(allsrc):
            g.add(f"backend/routers/{rf} {key}: dicatat 'cas' tetapi find_one_and_update induk tidak berprasyarat status.")
        if mech == "compensate" and not RE_COMP.search(allsrc):
            g.add(f"backend/routers/{rf} {key}: dicatat 'compensate' tetapi tidak ada `except → await release_/rollback` (kompensasi hilang).")
        if mech == "service" and svc_ref:
            ssrc = service_function_source(svc_ref)
            if ssrc is None:
                g.add(f"{rf} {key}: rujukan service '{svc_ref}' tidak ditemukan di backend/services.")
            elif not RE_CLAIM.search(ssrc) or not RE_FINISH.search(ssrc):
                g.add(f"backend/services/{svc_ref}: dicatat klaim di service tetapi tidak ada atomic_claim.claim() + finish_set/release.")
            elif (late := validation_after_claim(ssrc)):
                g.add(f"backend/services/{svc_ref}: validasi 4xx SESUDAH klaim (`{late[:70]}`) — kunci tertinggal.")
        if mech == "service_cas":
            ssrc = service_function_source(svc_ref or "")
            if ssrc is None:
                g.add(f"{rf} {key}: rujukan service '{svc_ref}' tidak ditemukan di backend/services.")
            elif not RE_CAS.search(ssrc):
                g.add(f"backend/services/{svc_ref}: dicatat 'service_cas' tetapi find_one_and_update di service tidak berprasyarat status/rfid_tag_id.")
    if unreviewed is not None:
        g.bump()
        if len(unreviewed) > baseline:
            g.add(f"BELUM DITINJAU = {len(unreviewed)} > baseline {baseline}. Endpoint multi-koleksi BARU wajib memakai "
                  "atomic_claim.claim()/CAS dan dicatat di REVIEWED: " +
                  "; ".join(f"{a} {b}" for a, b in unreviewed[:5]))
        elif len(unreviewed) < baseline:
            g.add(f"BELUM DITINJAU = {len(unreviewed)} < baseline {baseline}: turunkan BASELINE_UNREVIEWED ke {len(unreviewed)} (ratchet hanya turun).")
    return g


def self_test() -> int:
    fails = 0
    n_case = 0

    def report(name, ok, got):
        nonlocal fails, n_case
        n_case += 1
        fails += 0 if ok else 1
        print(f"  [{G if ok else R}{'PASS' if ok else 'FAIL'}{X}] {name} → {got}")

    def case(name, sources, reviewed, expect_red, unreviewed=None, baseline=0, helpers=None, units=None, expect_msg=""):
        g = check(sources, reviewed, unreviewed, baseline, helpers=helpers, units=units)
        red = bool(g.violations)
        ok = red == expect_red and (not expect_msg or any(expect_msg in v for v in g.violations))
        report(name, ok, "MERAH" if red else "hijau")

    K = ("r.py", "POST /x/{id}/go")
    good_claim = "async def f():\n    await _saga.claim('x', i, 'a')\n    await db.x.find_one_and_update({'id': i}, _saga.finish_set({'status': 'b'}))\n"
    no_finish = "async def f():\n    await _saga.claim('x', i, 'a')\n    await db.x.update_one({'id': i}, {'$set': {'status': 'b'}})\n"
    no_claim = "async def f():\n    await db.x.update_one({'id': i}, {'$set': {'status': 'b'}})\n"
    cas_ok = "async def f():\n    u = await db.x.find_one_and_update({'id': i, \"status\": {'$in': ['a']}}, {'$set': {}})\n"
    R1 = {K: ("claim", "alasan yang cukup panjang untuk lolos uji")}
    R2 = {K: ("cas", "alasan yang cukup panjang untuk lolos uji")}
    case("claim + finish_set → hijau", {K: good_claim}, R1, False)
    case("claim tanpa pencabut kunci → MERAH", {K: no_finish}, R1, True)
    case("dicatat claim tapi tak memanggil claim() → MERAH", {K: no_claim}, R1, True)
    late_400 = "async def f():\n    await _saga.claim('x', i, 'a')\n    if bad:\n        raise HTTPException(status_code=400, detail='x')\n    await db.x.find_one_and_update({'id': i}, _saga.finish_set({'status': 'b'}))\n"
    early_400 = "async def f():\n    if bad:\n        raise HTTPException(status_code=400, detail='x')\n    await _saga.claim('x', i, 'a')\n    await db.x.find_one_and_update({'id': i}, _saga.finish_set({'status': 'b'}))\n"
    case("validasi 400 SESUDAH klaim (kunci tertinggal) → MERAH", {K: late_400}, R1, True)
    case("validasi 400 SEBELUM klaim → hijau", {K: early_400}, R1, False)
    released_400 = "async def f():\n    await _saga.claim('x', i, 'a')\n    try:\n        await sub()\n    except Err:\n        await _saga.release('x', i)\n        raise HTTPException(status_code=400, detail='x')\n    await db.x.find_one_and_update({'id': i}, _saga.finish_set({'status': 'b'}))\n"
    case("validasi 400 sesudah klaim TAPI release() dulu → hijau", {K: released_400}, R1, False)
    case("cas berprasyarat status → hijau", {K: cas_ok}, R2, False)
    case("dicatat cas tapi tanpa prasyarat status → MERAH", {K: no_claim}, R2, True)
    comp_ok = "async def f():\n    try:\n        await reserve()\n    except HTTPException:\n        await release_order_rolls(i)\n        raise\n"
    R3 = {K: ("compensate", "alasan yang cukup panjang untuk lolos uji")}
    case("compensate dengan except→release → hijau", {K: comp_ok}, R3, False)
    case("dicatat compensate tanpa kompensasi → MERAH", {K: no_claim}, R3, True)
    R4 = {K: ("service", "alasan yang cukup panjang untuk lolos uji", "modul_tidak_ada.fungsi")}
    case("service merujuk fungsi yang tak ada → MERAH", {K: no_claim}, R4, True)
    R5 = {K: ("service", "alasan yang cukup panjang untuk lolos uji", "putaway_order_service.confirm_arrival")}
    case("service nyata berklaim (putaway confirm_arrival) → hijau", {K: no_claim}, R5, False)
    # PK-33 — rujukan lama (`putaway_order_service.dispatch`) kini berklaim (PREP-C), jadi kasus merahnya diganti fungsi
    # layanan yang memang tidak pernah mengklaim: `atomic_claim.finish_set` (hanya membangun dokumen update).
    R6 = {K: ("service", "alasan yang cukup panjang untuk lolos uji", "atomic_claim.finish_set")}
    case("service nyata TANPA klaim (atomic_claim.finish_set) → MERAH", {K: no_claim}, R6, True)
    R7 = {K: ("service_cas", "alasan yang cukup panjang untuk lolos uji", "rfid_service.retire_tag")}
    case("service_cas nyata berprasyarat status (retire_tag) → hijau", {K: no_claim}, R7, False)
    R8 = {K: ("service_cas", "alasan yang cukup panjang untuk lolos uji", "atomic_claim.release")}
    case("service_cas nyata TANPA find_one_and_update berprasyarat (atomic_claim.release) → MERAH", {K: no_claim}, R8, True)
    case("entri REVIEWED basi (endpoint hilang) → MERAH", {}, R1, True)
    case("alasan pendek → MERAH", {K: good_claim}, {K: ("claim", "pendek")}, True)
    case("BELUM DITINJAU naik di atas baseline → MERAH", {}, {}, True, unreviewed=[("a.py", "POST /b")], baseline=0)
    case("BELUM DITINJAU turun di bawah baseline → MERAH (turunkan baseline)", {}, {}, True, unreviewed=[], baseline=1)
    case("BELUM DITINJAU == baseline → hijau", {}, {}, False, unreviewed=[("a.py", "POST /b")], baseline=1)

    # ── PK-33 B.5 — pencacah: nama polos tidak lagi dihitung (dua arah) ─────────────────────────────────────────────
    idx = {"ocr_sample_service.delete": {"ocr_samples"}, "ocr_sample_service.update": {"ocr_samples"}}
    tanpa_impor = ("@router.delete('/a/{i}')\nasync def f(i):\n    await db.alpha.delete_one({'id': i})\n"
                   "    x.delete(i)\n    d = {}\n    d.update({'k': 1})\n")
    rows = inv.rows_for_source("r.py", tanpa_impor, idx)
    report("pencacah: `x.delete`/`d.update` TANPA impor layanan tidak dihitung → 0 baris", rows == [], f"{len(rows)} baris")
    impor_modul = "from services import ocr_sample_service as x\n" + tanpa_impor
    rows = inv.rows_for_source("r.py", impor_modul, idx)
    report("pencacah: `from services import X as x` + `x.delete` → dihitung (alpha+ocr_samples)",
           [r[5] for r in rows] == [["alpha", "ocr_samples"]], f"{[r[5] for r in rows]}")
    impor_fungsi = ("@router.post('/a/{i}/go')\nasync def f(i):\n    from services.ocr_sample_service import update as ubah\n"
                    "    await db.alpha.update_one({'id': i}, {})\n    await ubah(i)\n")
    rows = inv.rows_for_source("r.py", impor_fungsi, idx)
    report("pencacah: `from services.X import fn as g` di badan endpoint + `g()` → dihitung, bermetode POST",
           [(r[2], r[5]) for r in rows] == [("POST /a/{i}/go", ["alpha", "ocr_samples"])], f"{[(r[2], r[5]) for r in rows]}")

    # ── PK-33 B.5 — path persis & dua metode pada path sama ─────────────────────────────────────────────────────────
    row = lambda key: ("r.py", 1, key, ["a"], {}, ["a", "b"])  # noqa: E731
    un = unreviewed_rows({("r.py", "POST /x"): ("none", "x" * 30)}, [row("POST /x/{id}/go")])
    report("path persis: entri 'POST /x' TIDAK menutupi 'POST /x/{id}/go' → tetap belum ditinjau",
           un == [("r.py", "POST /x/{id}/go")], f"{un}")
    case("path persis: entri 'POST /x' untuk endpoint yang hanya ada '/x/{id}/go' → MERAH (basi)",
         {K: good_claim}, {("r.py", "POST /x"): ("claim", "alasan yang cukup panjang untuk lolos uji")}, True)
    KD, KP = ("r.py", "DELETE /x/{id}"), ("r.py", "PATCH /x/{id}")
    RD = {KD: ("claim", "alasan yang cukup panjang untuk lolos uji")}
    case("dua metode path sama: entri DELETE diperiksa pada fungsi DELETE (berklaim) → hijau",
         {KP: no_claim, KD: good_claim}, RD, False)
    case("dua metode path sama: fungsi DELETE tanpa klaim (PATCH berklaim) → MERAH",
         {KP: good_claim, KD: no_claim}, RD, True)
    un = unreviewed_rows(RD, [row("PATCH /x/{id}"), row("DELETE /x/{id}")])
    report("dua metode path sama: entri DELETE tidak menutupi PATCH → PATCH tetap belum ditinjau",
           un == [("r.py", "PATCH /x/{id}")], f"{un}")
    case("kunci tanpa metode HTTP → MERAH", {("r.py", "/x/{id}/go"): good_claim},
         {("r.py", "/x/{id}/go"): ("claim", "alasan yang cukup panjang untuk lolos uji")}, True)
    case("mekanisme tak dikenal → MERAH", {K: good_claim}, {K: ("aman", "alasan yang cukup panjang untuk lolos uji")}, True)

    # ── PK-33 B.3 — pola di pembantu modul router yang sama (satu tingkat) ──────────────────────────────────────────
    calls_helper = "async def f():\n    return await _tutup(po)\n"
    helper_cas = "async def _tutup(po):\n    await db.po.find_one_and_update({'id': po['id'], \"status\": po['status']}, {'$set': {}})\n"
    helper_claim = "async def _tutup(po):\n    await _saga.claim('po', i, 'a')\n    await db.po.find_one_and_update({'id': i}, _saga.finish_set({}))\n"
    case("cas di pembantu modul yang sama → hijau", {K: calls_helper}, R2, False, helpers={K: [helper_cas]})
    case("cas: endpoint memanggil pembantu TANPA prasyarat → MERAH", {K: calls_helper}, R2, True, helpers={K: [no_claim]})
    case("claim di pembantu modul yang sama → hijau", {K: calls_helper}, R1, False, helpers={K: [helper_claim]})
    case("claim: pembantu tidak dipanggil (tidak ada di peta pembantu) → MERAH", {K: calls_helper}, R1, True, helpers={})
    late_helper = helper_claim.replace("    await db.po", "    raise HTTPException(status_code=400, detail='x')\n    await db.po")
    case("claim di pembantu, validasi 400 SESUDAH klaim di pembantu → MERAH", {K: calls_helper}, R1, True, helpers={K: [late_helper]})

    # ── PK-33 B.3 — pola RE_CAS baru, masing-masing dua arah ────────────────────────────────────────────────────────
    em_ok = "async def f():\n    c = await db.vb.find_one_and_update(\n        {\"id\": b, \"payments\": {\"$elemMatch\": {\"id\": p, \"voided\": {\"$ne\": True}}}}, {})\n"
    em_no = "async def f():\n    c = await db.vb.find_one_and_update(\n        {\"id\": b, \"payments\": {\"$elemMatch\": {\"id\": p}}}, {})\n"
    case("RE_CAS $elemMatch berprasyarat unsur larik ($ne) → hijau", {K: em_ok}, R2, False)
    case("RE_CAS $elemMatch hanya mencocokkan id (tanpa prasyarat) → MERAH", {K: em_no}, R2, True)
    pas_ok = "async def f():\n    await place_roll(roll, wh, node, actor=a, cas={\"status\": \"receiving\"})\n"
    pas_no = "async def f():\n    await place_roll(roll, wh, node, actor=a)\n"
    case("RE_CAS prasyarat status diteruskan ke penulis (cas={\"status\"…}) → hijau", {K: pas_ok}, R2, False)
    case("RE_CAS penulis dipanggil tanpa prasyarat cas= → MERAH", {K: pas_no}, R2, True)
    del_ok = "async def f():\n    r = await db.rolls.delete_one({\"id\": i, \"status\": \"receiving\"})\n"
    del_no = "async def f():\n    r = await db.rolls.delete_one({\"id\": i})\n"
    case("RE_CAS hapus bersyarat status → hijau", {K: del_ok}, R2, False)
    case("RE_CAS hapus tanpa syarat status → MERAH", {K: del_no}, R2, True)

    nd_ok = ("async def f():\n    _cas = {\"id\": i, \"status\": \"waiting\"}\n"
             "    u = await db.po.find_one_and_update(\n        _cas, {\"$set\": {}})\n")
    nd_no = ("async def f():\n    _cas = {\"id\": i}\n    u = await db.po.find_one_and_update(\n        _cas, {\"$set\": {}})\n")
    case("RE_CAS filter bernama berisi status → find_one_and_update(_cas, …) → hijau", {K: nd_ok}, R2, False)
    case("RE_CAS filter bernama TANPA status → MERAH", {K: nd_no}, R2, True)
    nu_ok = ("async def f():\n    _cas = {\"id\": i, \"status\": s}\n    res = await db.po.update_one(_cas, {\"$set\": u,\n"
             "                                       \"$push\": {}})\n    if not res.modified_count:\n        raise X\n")
    nu_no = nu_ok.replace("    if not res.modified_count:\n        raise X\n", "    return res\n")
    case("RE_CAS update_one(filter bernama berstatus) + modified_count diperiksa → hijau", {K: nu_ok}, R2, False)
    case("RE_CAS update_one(filter bernama berstatus) TANPA memeriksa hasil → MERAH", {K: nu_no}, R2, True)
    ui_ok = ("async def f():\n    lock = await db.c.update_one({\"id\": s, \"status\": {\"$ne\": \"merged\"}},\n"
             "                                {\"$set\": {\"merge_lock\": t}})\n    if not lock.modified_count:\n        raise X\n")
    ui_no = ui_ok.replace("    if not lock.modified_count:\n        raise X\n", "")
    case("RE_CAS update_one berprasyarat status + modified_count diperiksa → hijau", {K: ui_ok}, R2, False)
    case("RE_CAS update_one berprasyarat status TANPA memeriksa hasil → MERAH", {K: ui_no}, R2, True)
    hc_ok = "async def f():\n    res = await db.inventory_rolls.update_one(held_cas(roll), {\"$set\": {}})\n"
    hc_no = "async def f():\n    res = await db.inventory_rolls.update_one({\"id\": roll[\"id\"]}, {\"$set\": {}})\n"
    case("RE_CAS update_one(held_cas(roll)) → hijau", {K: hc_ok}, R2, False)
    case("RE_CAS update_one roll tanpa held_cas → MERAH", {K: hc_no}, R2, True)
    emu_ok = ("async def f():\n    res = await db.mko.update_one(\n        {\"id\": m, \"saga_lock\": {\"$exists\": False},\n"
              "         \"steps\": {\"$elemMatch\": {\"seq\": q, \"status\": \"issued\"}}}, {})\n")
    emu_no = emu_ok.replace("\"status\": \"issued\"", "\"seq2\": q")
    case("RE_CAS update_one $elemMatch berprasyarat status unsur → hijau", {K: emu_ok}, R2, False)
    case("RE_CAS update_one $elemMatch tanpa prasyarat → MERAH", {K: emu_no}, R2, True)
    # ── PK-33 — klaim lewat alias `saga` + pelepasan di `finally:` ────────────────────────────────────────────────
    alias_ok = ("async def f():\n    from services import atomic_claim as saga\n    await saga.claim('x', i, 'a')\n"
                "    try:\n        out = await sub()\n    except ValueError as e:\n"
                "        raise HTTPException(status_code=400, detail=str(e))\n    finally:\n        await saga.release('x', i)\n")
    alias_no = alias_ok.replace("        await saga.release('x', i)\n", "        pass\n")
    case("claim alias `saga` + release di finally (400 di dalam try) → hijau", {K: alias_ok}, R1, False)
    case("claim alias `saga`, finally TANPA release → MERAH", {K: alias_no}, R1, True)

    # ── PK-33 B.4 — mekanisme `unit` ─────────────────────────────────────────────────────────────────────────────────
    UNITS = {"PK-99": "dikerjakan", "PK-98": "selesai", "PK-97": "tervalidasi", "PK-96": "siap"}
    RU = lambda r: {K: ("unit", r)}  # noqa: E731
    case("unit: ID dikenal, status dikerjakan → hijau", {K: no_claim}, RU("PK-99: jalur tulis ini diganti satu pintu oleh unit itu"), False, units=UNITS)
    case("unit: ID dikenal, status siap → hijau", {K: no_claim}, RU("PK-96: jalur tulis ini diganti satu pintu oleh unit itu"), False, units=UNITS)
    case("unit: ID tak dikenal di INDEKS_UNIT → MERAH", {K: no_claim}, RU("PK-00: jalur tulis ini diganti satu pintu oleh unit itu"), True,
         units=UNITS, expect_msg="tidak dikenal")
    case("unit: status selesai → MERAH (basi, sebut unit sudah selesai)", {K: no_claim}, RU("PK-98: jalur tulis ini diganti satu pintu oleh unit itu"), True,
         units=UNITS, expect_msg="sudah selesai")
    case("unit: status tervalidasi → MERAH", {K: no_claim}, RU("PK-97: jalur tulis ini diganti satu pintu oleh unit itu"), True, units=UNITS)
    case("unit: alasan sesudah ID < 20 huruf → MERAH", {K: no_claim}, RU("PK-99: diganti unit itu sendiri"[:20]), True, units=UNITS)
    case("unit: alasan tanpa awalan ID → MERAH", {K: no_claim}, RU("jalur tulis ini diganti satu pintu oleh unit lain"), True, units=UNITS)
    st = unit_statuses("| 1 | PK-99 | a | — | r |\n| 2 | PK-98 | b | — | r |\n", "| 1 | PK-99 | a | — | dikerjakan |  |\n| 2 | PK-98 | b | — | selesai | x |\n")
    report("unit_statuses membaca ID dari INDEKS dan status dari STATUS", st == {"PK-99": "dikerjakan", "PK-98": "selesai"}, f"{st}")
    # ── PK-33 U10 — alasan `none` yang hanya berbunyi "aman" ─────────────────────────────────────────────────────────
    case("none: alasan hanya 'aman …' (tanpa MENGAPA) → MERAH", {K: no_claim}, {K: ("none", "aman. aman, aman — aman; aman aman")}, True)
    case("none: alasan menyebut mengapa ulangan aman → hijau", {K: no_claim},
         {K: ("none", "satu dokumen $set nilai sama; ulangan menulis nilai yang sama")}, False)

    real = check(endpoint_sources(), REVIEWED, unreviewed_rows(), helpers=helper_sources())
    ok = not real.violations
    report(f"kode nyata saat ini HIJAU ({len(real.violations)} pelanggaran)", ok, "hijau" if ok else "MERAH")
    for v in real.violations:
        print(f"    ✗ {v[:200]}")
    print(f"{G if not fails else R}  SELF-TEST {'HIJAU' if not fails else 'MERAH'} ({n_case} kasus, {fails} gagal).{X}")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    return check(endpoint_sources(), REVIEWED, unreviewed_rows(), helpers=helper_sources()).finish()


if __name__ == "__main__":
    sys.exit(main())

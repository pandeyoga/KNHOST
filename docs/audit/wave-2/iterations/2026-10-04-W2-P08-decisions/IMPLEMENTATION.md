# P08 — Implementasi W2-REQ-01 s/d 09

Kandidat: basis `1bafcda` + perubahan sesi 2026-10-04 (working tree, di-commit otomatis platform). Kontrak: [DECISIONS.md](DECISIONS.md).
Regresi: `regression_p08_fase1.py` (REQ-01/03, W2-025 turunan) dan `regression_p08_fase2_6.py` (36/36 lulus, data sintetis TEST_P08B_*, self-clean).

| ID | Perubahan | File utama | Bukti |
|---|---|---|---|
| REQ-01 | `recorded_by` otomatis + `performed_by_user_id` wajib saat submit round; histori menampilkan keduanya. REQ-01b: tanpa izin per jenis uji (keputusan pemilik). | routers/rnd.py, rnd_sample_service.py, RoundActionModal.jsx | fase1 + iteration_141 |
| REQ-03 | Uji wajib per lini (woven/knit labdip+handfeel; printing proofing) = PERINGATAN; decide/approve_spec/release tanpa alasan override → 422, dengan alasan → sukses + tercatat. Bahan standar tidak terkena. | services/rnd_required_tests.py, DecideModal.jsx, requiredTests.js | fase1 |
| REQ-09 | `target_quantity` + `rounding_choice` di baris SO roll; server menolak finalisasi tanpa pilihan/arah salah (422), qty baris ≠ total roll (422), potong roll tanpa `order.exact_cut` (403). Prefix FEFO mengikuti urutan (900 vs 805 diuji dua urutan). Ringkasan roll/total/selisih tampil; tidak ada pilihan default kecuali kombinasi pas. Ringkasan disimpan di `items[].roll_rounding`. | sales_order_helpers.assert_roll_rounding, sales_orders.py, RollReconcileSheet.jsx, ProductQuickView/MobileQuickView, useAppActions | REQ09-* |
| REQ-08 | Dispatch tanpa loading check menolak roll SO tanpa tag RFID aktif (juga gudang `optional`). Pengecualian roll tanpa tag di loading check butuh izin baru `wms.untagged_override` (admin/manager/warehouse_admin) + alasan, tercatat di sesi (`untagged_exceptions`) & audit. Putaway (stage `tag_verified`) dan cross-dock (`cross_dock_ready` hanya dari tag terverifikasi) sudah menolak sejak sebelumnya. SJ = 1 shipment per task outbound per gudang (shipment_service.dispatch_task) — perilaku lama dipertahankan. RFID-03 ditautkan, bukan tiket baru. | loading_check_service.py, outbound_picking.py, LoadingCheckPanel.jsx, permissions_config.py | REQ08-* |
| REQ-06 | Saat GRN ditutup dan baris PO kurang terima di luar toleransi → `po_variance_tasks` (idempoten) untuk MD penanggung jawab (fallback pembuat PO) + notifikasi; PO ber-DP/bayar/tagihan → notifikasi Finance. Keputusan wajib alasan: tunggu (tugas sisa), amendment (status `pending_amendment`, selesai saat amandemen PO + re-approval yang ada), short-close (nilai/tagihan tidak diubah). Snapshot `before` dicatat. API `GET /api/po-variance-tasks`, `POST /api/po-variance-tasks/{id}/decide`. | po_variance_task_service.py, purchase_orders_extra.py, goods_receipt_close_service.py, POVarianceTasksPanel.jsx | REQ06-* |
| REQ-04 | Papan stok POV sales: angka utama = `global_total` grup (tanpa owner/biaya), baris kecil "entitas saya" = siap dijanjikan; ATP diberi label tersedia+incoming. | InventoryStatusBoard.jsx | REQ04-* |
| REQ-05 | Form PO menampilkan entitas pembeli + ganti cepat (hanya entitas switcher yang diizinkan); draft disimpan ke sessionStorage lalu dipulihkan setelah layar entitas baru dimuat (gudang dipilih ulang). Backend tetap memakai entitas aktif. | POBuyerEntitySwitch.jsx, PurchaseOrderManagement.jsx, POCreateForm.jsx, App.js, AppViewRouter.jsx | UI — perlu uji browser |
| REQ-07 | `material_reservations` (soft, tanpa jurnal/fisik) dibuat saat PR makloon `approved` (create/submit/approve) dari resep: output ÷ (yield×(1−susut)); shortage dicatat. Realisasi PR→MKO memindah reservasi; issue step 1 mengonsumsi; issue MKO lain ditolak 409 bila bahan dicadangkan pihak lain; cancel/reject PR, cancel MKO melepas; ubah qty PR → replan. API `GET /api/material-reservations`. | material_reservation_service.py, purchase_requisition_service.py, pr_sourcing_service.py, makloon_order_service.py | REQ07-* |
| REQ-02 | Preview legacy (kosong/tidak kanonik/konflik/kandidat duplikat atribut kanonik) tanpa menulis; eksekusi batch hanya dari usulan preview + tanda tangan preview (409 bila basi); rollback per batch mengembalikan snapshot; koreksi nama tanpa ubah SKU + `name_history`. UI di Katalog → "Tata kelola master". | master_governance_service.py, routers/master_governance.py, MasterGovernancePanel.jsx | REQ02-* |

## Skema baru
`po_variance_tasks`, `material_reservations`, `master_governance_batches`; field `sales_orders.items[].roll_rounding`, `products.name_history`, `rfid_verify_sessions.untagged_exceptions`; izin `order.exact_cut`, `wms.untagged_override` (di-merge otomatis oleh bootstrap). Pemulihan: hapus koleksi baru; field tambahan bersifat aditif.

## Ditunda / butuh keputusan pemilik
Standar penamaan perusahaan (tidak dikarang), alias kode warna customer, COMM-04 & 4 kasus owner-questions-P21 Wave1.

## Batas uji
- REQ-07: perhitungan resep diuji lewat `makloon_prefill` yang sudah ada; uji regresi memakai reservasi sintetis langsung (bukan PR end-to-end dengan resep), tidak menguji multi-step/owner berbeda.
- REQ-07: reservasi mengurangi ketersediaan untuk reservasi & issue makloon lain; alokasi SO atas bahan input yang sama belum membaca reservasi ini.
- REQ-08: printer/reader fisik dan SO 3 gudang → 3 SJ belum UAT di browser/perangkat.
- REQ-05/REQ-04/REQ-06 UI: belum diuji browser oleh agent pengujian pada sesi ini.
- Uji lama `tests/test_iter265_r3r4r5.py` 13 gagal sebelum & sesudah perubahan (pesan/seed device usang), tidak terkait.

# IMPLEMENTATION

Commit sumber diuji: patch di atas `b25ff3b` (working tree; SHA kandidat diisi setelah commit platform).
ID/fase: P04 — FN-01, FN-02, FN-11, IX-16.

Reproduksi HEAD sebelum patch: `git worktree add .head_wt b25ff3b && cd .head_wt/backend && python ../../audit/iterations/2026-10-03-P04-costing/repro_p04.py` → [head_before_patch.txt](head_before_patch.txt) `pass=1 fail=6`: landed cost 100 menaikkan nilai stok >100 (anak dihitung ganda), 60+60 vs diterima 100 lolos `matched`, HPP shipment memakai rata-rata (2.000/2.000, bukan 1.000/3.000) tanpa snapshot biaya, retur 111 menjurnal Dr 100 sementara AP turun 111.

Perubahan dan kontrak lintas caller:
- FN-01 `landed_cost_service`: target alokasi = SELURUH fragmen fisik (turunan via parent/root ikut, termasuk potongan lama tanpa `acquired.ref_id`); propagasi KN-B17 ke turunan dihapus; increment per roll dijaga `landed_cost_refs ≠ voucher` (retry idempotent). Konservasi: Σ(Δunit_cost × length_initial) = nilai voucher.
- FN-02 `vendor_bill_service.evaluate_match`: qty baris sebelumnya pada tagihan yang sama ikut mengurangi sisa; `routers/vendor_bills.py` menolak baris produk ganda (400).
- FN-11 `roll_service.ship_order_rolls`: `shipments.rolls[]` membekukan `unit_cost` + `extended_cost` per roll keluar; `gl_service.post_shipment_cogs` memakai Σ extended_cost bila snapshot lengkap (surat jalan lama → rata-rata lama).
- IX-16 `purchase_return_service`: satu nilai gross (`grand_total` = net + PPN) untuk AP (`returned_amount`), GL (Dr Hutang/GR-IR/Kas gross, Cr Persediaan net, Cr PPN) dan kas refund.

Regression test: `cd backend && python ../audit/iterations/2026-10-03-P04-costing/repro_p04.py` → [after_patch.txt](after_patch.txt) `pass=7 fail=0`.
Kontrol yang dipertahankan: toleransi qty/harga/rupiah 3-way, idempotensi `shipment_cogs`/`purchase_return`, basis alokasi value/quantity.
Data historis/migration dry-run: tidak ada migrasi; voucher landed cost lama yang sudah dipropagasi ganda tidak dikoreksi otomatis (perlu event koreksi terpisah); surat jalan lama tanpa snapshot tetap memakai rata-rata.
Batas pengujian: FN-02 belum mencocokkan per PO line ID (PO dengan produk sama di dua harga masih digabung per product_id) dan belum ada klaim atomik untuk dua tagihan bersamaan; IX-16 hanya jalur approve langsung (jalur RMA supplier_accept memakai fungsi finalisasi yang sama).
ID siap divalidasi / tertunda: FN-01, FN-02, FN-11, IX-16 in_progress (menunggu SHA).

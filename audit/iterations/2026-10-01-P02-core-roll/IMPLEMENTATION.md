# IMPLEMENTATION

Commit sumber diuji: patch di atas `0076f7ea16ddc93d5b01f480768418464c5c3347` (working tree; SHA kandidat diisi setelah commit platform). Diff: [session2_combined.diff](session2_combined.diff).
ID/fase: P02 — WM-01, AX-07, AX-05, FN-03, IX-13, GN-12, GN-13 dipatch; WM-02, GN-15 direbaseline (masih ada, tertunda).

Reproduksi HEAD sebelum patch: `cd backend && python ../audit/iterations/2026-10-01-P02-core-roll/repro_p02.py` → [head_before_patch.txt](head_before_patch.txt) `pass=1 fail=10`:
- WM-01: 5 split bersamaan → 3 gagal `DuplicateKeyError uq_roll_no` SETELAH induk dikurangi; normalisasi menulis nilai basi (induk 8.0 padahal 5 potongan diminta) → reservasi gagal/stok kacau. Temuan tambahan pada jalur sama: nomor potongan tidak atomik.
- AX-07: parent cucu = root (bukan anak).
- AX-05: `acquired` jadi `transfer`, bin BIN-W1 terbawa ke W2, landed cost PO tidak menemukan roll.
- FN-03: WAC 47.860 (yard+meter dicampur) — seharusnya 50.000/m.
- GN-13: unit tak dikenal dijumlahkan mentah (29.14); tulis rebuild basi diterima.
- GN-12: WAC 5.002 roll = 10.000 (roll ke-5.002 terpotong).
- IX-13: statis [head_ix13_static.txt](head_ix13_static.txt) — 100 cm → task 100 meter.

Perubahan dan kontrak lintas caller:
- WM-01 `_split_roll`: kurang+bulat dalam satu update pipeline atomik; `insert_child_roll` mengulang nomor saat DuplicateKey (roll_no) sehingga induk yang sudah dikurangi selalu punya potongan.
- AX-07 `insert_child_roll`: `parent_roll_id` = roll yang dipotong, `root_roll_id` = root induk (eksplisit, bukan setdefault).
- AX-05 `receive_wh_transfer_rolls` (owner tetap): `acquired` tidak ditimpa; `bin_id=None` sampai putaway; `last_transfer` dicatat.
- FN-03/GN-12 `wac_for_product`: panjang dikonversi ke base unit via konverter kanonik; nilai = cost/unit roll × qty roll; roll tanpa faktor dikecualikan (`unconvertible_rolls`); iterasi kursor tanpa cap.
- GN-13/GN-12 `rebuild_balance`: tiket rebuild diambil sebelum baca; tulis hanya bila `rebuild_applied < tiket`; roll tak terkonversi tidak dijumlahkan → `projection_valid=false`, `unconvertible_roll_count`; tanpa cap 10.000. `financial_statement_service` iterasi kursor; ringkasan kas difilter entitas di DB tanpa cap 2.000.
- IX-13: `receiving_roll_service.uom_engine/conv_qty` (uom_service.convert + aturan pasangan) dipakai di scan label, hitung manual, dan konfirmasi ukuran (`inbound_scan_label`); unit tanpa faktor → 400 sebelum roll/tag/counter.

Regression test: `repro_p02.py` 13/13 [after_patch.txt](after_patch.txt). Suite GRN/reallocate: kegagalan level-suite bergantung state data dan juga terjadi di HEAD ([legacy_suite_head.txt](legacy_suite_head.txt) vs [legacy_suite_after.txt](legacy_suite_after.txt)); dijalankan terisolasi setelah patch 11 passed/2 skipped ([legacy_suite_isolated_after.txt](legacy_suite_isolated_after.txt)); 2 kegagalan GRN (`test_require_grade_legacy_map`, `test_grn_mode_blocks_new_legacy_receipts_but_not_in_flight`) identik di HEAD.
Kontrol yang dipertahankan: CAS split (roll non-available/kurang panjang → None); transfer antar-entitas tetap menulis `acquired`+history; rebuild tetap upsert segmen baru.
Data historis/migration dry-run: tidak ada migrasi otomatis. DB sintetis: 2 roll `acquired.via=transfer` (asal PO tidak dapat dipulihkan tanpa bukti movement → perlu rekonsiliasi manual); `parent_roll_id` lama yang salah tidak direkonstruksi (butuh dry-run diff); balance lama tanpa `rebuild_applied` diperlakukan tiket 0.
Batas pengujian: konkurensi diuji pada satu proses motor (interleaving await), belum multi-worker; laporan keuangan 100k+ jurnal tidak diuji beban.
Tertunda: WM-02 (reservasi parsial membuat roll anak sebelum potong fisik — perlu model reservasi panjang pada induk; perubahan desain alokasi/picking), GN-15 (duplikasi helper/status, P3 — sebagian berkurang: konversi penerimaan kini satu jalur kanonik; `_roll_view` tampilan masih memakai faktor lokal).

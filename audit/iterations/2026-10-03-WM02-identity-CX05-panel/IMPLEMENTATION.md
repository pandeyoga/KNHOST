# IMPLEMENTATION

Commit sumber diuji: patch di atas `b25ff3b` (working tree; SHA kandidat diisi setelah commit platform).
ID/fase: WM-02 lanjutan (tag roll anak wajib sebelum muat/kirim, picker panjang bebas), CX-05 (keputusan pemilik: kelebihan LPJ → Hutang Reimburse Karyawan; 1 LPJ per PD dipertahankan), Panel Posting Gagal.

Reproduksi HEAD sebelum patch: `cd .head_wt/backend && python ../../audit/iterations/2026-10-03-WM02-identity-CX05-panel/repro_followup.py` → [head_before_patch.txt](head_before_patch.txt) `pass=0 fail=1 crashed=1`: picker menyembunyikan roll induk yang dipesan sebagian, dan beli-per-roll sebagian pada induk itu gagal 409 ("keburu berubah").

Perubahan:
- `roll_service.assert_cut_identity_ready` dipakai `ship_order_rolls` + `loading_check_service.start`: 409 bila masih ada reservasi potong ATAU roll anak `cut.identity_verified=false`. Potong otomatis saat dispatch (`at_dispatch`, sesi 2026-10-02) DIHAPUS.
- `mark_cut_identity_verified` dipanggil `rfid_print_service.complete_verify` (roll anak ber-tag yang terbaca → sah); tanpa `rfid_tag_id` tidak disahkan. `set_journey` menerima tahap `cut_pending_tag`.
- Picker `list_available_rolls`: induk berreservasi potong tampil dengan `length_remaining` = panjang bebas + `physical_length`, `length_reserved`.
- `reserve_specific_rolls` (beli per roll, ref SO): ambil sebagian / induk berreservasi = reservasi panjang; melebihi panjang bebas 400; ref non-SO pada induk berreservasi 409. `sales_order_helpers` "roll utuh" = panjang bebas. `_release_rolls_by_ref_id` ikut melepas reservasi panjang.
- Ganti Roll (`sales_orders_extra.reallocate_line_rolls`): reservasi potong baris dianggap roll lama; yang tidak dipilih dilepas (temuan tambahan: sebelumnya tertinggal yatim → invariant backorder merah pada SO uji).
- CX-05 `gl_service.post_petty_cash_settlement(advance_amount)`: Cr 1-1400 dibatasi nilai PD, kelebihan Cr 2-1650 Hutang Reimburse Karyawan (akun baru di COA default).
- Panel Posting Gagal: `GET /api/finance/posting-failures` (kas, kwitansi AR, retur beli, GR, surat jalan; izin accounting.view, terbatas entitas) + `POST /api/finance/posting-failures/{kind}/{id}/retry` (accounting.manage, jalur idempotent tiap modul). FE: menu Keuangan → **Posting Gagal** (`posting-failures-view`, `pf-retry-<id>`, `pf-filter-<kind>`).
- `scripts/verify_data_integrity.py`: proyeksi saldo mengenal reservasi panjang (WM-02); F402 `field` di INV-NUM-01 diganti nama.

Regression test: `cd backend && python ../audit/iterations/2026-10-03-WM02-identity-CX05-panel/repro_followup.py` → [after_patch.txt](after_patch.txt) `pass=13 fail=0`. `repro_wm02.py` (2026-10-02) diperbarui: dispatch sebelum potong kini diharapkan 409 → `pass=11`.
Legacy: `tests/test_roll_pick_and_reallocate.py` + `tests/test_allocation_policy_17.py` 8 passed/1 skipped; integritas PASS 248 · FAIL 0 (setelah SO uji residu KSC/SO-00019 dengan reservasi yatim dihapus).
Batas pengujian: bagian HTTP skrip memakai server yang berjalan (sudah terpatch) sehingga tidak menjadi bukti HEAD; verifikasi identitas hanya lewat sesi RFID (tanpa jalur label/barcode manual); pembayaran Hutang Reimburse lewat kas manual (belum ada alur khusus).
ID: WM-02 in_progress; CX-05 in_progress (keputusan pemilik tercatat).

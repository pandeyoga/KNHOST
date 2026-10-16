# IMPLEMENTATION

Commit sumber diuji: patch di atas `49b177090d57a1d349830c83f7f53c119cb17631` (working tree; SHA kandidat diisi setelah commit platform).
ID/fase: P06 — AX-08, WM-03, WM-04, WM-05, WM-09, IX-09.

Reproduksi HEAD sebelum patch: `cd .head_src/backend && python ../../audit/iterations/2026-10-02-P06-receiving/repro_p06.py` → [head_before_patch.txt](head_before_patch.txt) `pass=0 fail=2 crashed=1`: roll quarantine bertag terverifikasi DITERIMA PA (AX-08); dua PA serentak satu roll keduanya lolos (WM-05) → skrip crash di langkah berikut.

Perubahan dan kontrak lintas caller (`services/putaway_order_service.py`, `routers/putaway_orders.py`):
- AX-08: PA hanya untuk roll `available` (bukan quarantine/reserved/hold), panjang > 0, tanpa perpindahan aktif; saran putaway memfilter hal sama. `complete_verify` (rfid_print_service) tidak lagi memundurkan journey roll yang sudah di tahap lain ke `tag_verified` (`set_journey(only_from=…)`).
- WM-05: klaim per roll `active_movement {type: putaway, id, number}` atomik (CAS status/gudang/journey/`active_movement: null`), all-or-none dengan rilis klaim; arrival/resolve CAS `active_movement.id == PA` + gudang asal + status.
- WM-04: dispatch (saga claim) memindah roll `available → in_transit_transfer` + rebuild saldo asal (ATP turun, owned tetap, transit terlapor); satu roll berubah → kompensasi seluruh PA, 409.
- WM-03: `scanned_epcs=[]` = nol roll tiba; `null` → 400; override `manual_all` wajib alasan ≥10 huruf + izin `wms.approve`, jejak `manual_override {by, reason, at}`. FE: kotak kosong mengirim `[]`, tombol baru `pa-confirm-manual-<id>`.
- WM-09: `_land_items` = satu jalur posting untuk arrival normal & accept exception: pasangan `putaway_transfer_out/in` (reference_id, reason, created_by), rebuild dua lokasi, counters dari hasil nyata; retry tidak menggandakan (item tidak lagi exception). `return_transit` mengembalikan status available + lepas klaim.
- IX-09: `inspection_service.reopen` → `return_service.unmark_inspected_by_document` mengosongkan `sales_returns.inspect_done_at`, riwayat di `inspect_reopen_history`.

Regression test: `cd backend && python ../audit/iterations/2026-10-02-P06-receiving/repro_p06.py` → [after_patch.txt](after_patch.txt) `pass=12 fail=0`.
Legacy: `tests/test_iter264_putaway_fixes.py` 2 passed, 1 failed `test_grade_b_group_includes_retur` — data demo tidak memiliki gudang "Retur" (4 gudang seed), bergantung fixture, bukan akibat patch.
Kontrol yang dipertahankan: saga claim PA, storage_rules, BTG hanya bila ada roll tiba, pemilik tidak berubah.
Data historis/migration dry-run: PA `open/in_transit` lama tidak punya `active_movement` → arrival CAS gagal → item jadi exception (perlu resolve/return_transit manual). Dry-run DB demo: `putaway_orders` open/in_transit = 0 saat diuji.
Batas pengujian: gate evaluator cabang PA (P09) belum diubah; reservasi SO masih dapat mengambil roll PA `open` (dispatch lalu 409 dan harus dibuat ulang); konkurensi diuji satu proses.
ID siap divalidasi / tertunda: AX-08, WM-03, WM-04, WM-05, WM-09, IX-09 in_progress (menunggu SHA). IX-15 ditangani sesi sebelumnya.

# IMPLEMENTATION

Commit sumber diuji: patch di atas `49b177090d57a1d349830c83f7f53c119cb17631` (working tree; SHA kandidat diisi setelah commit platform).
ID/fase: P02 — WM-02 (reservasi parsial tanpa roll anak sebelum potong fisik).

Reproduksi HEAD sebelum patch: `cd .head_src/backend && python ../../audit/iterations/2026-10-02-P02-wm02-reservation/repro_wm02.py` → [head_before_patch.txt](head_before_patch.txt) `pass=1 fail=3 crashed=1`: reserve 30 dari roll 100 langsung membuat roll anak (2 roll di DB, induk 70) dan kontrak reservasi panjang belum ada.

Perubahan dan kontrak lintas caller (`services/roll_service.py`):
- `_reserve_length`: reservasi PANJANG di induk (`length_reservations[]`, `length_reserved`) dengan CAS atomik `length_remaining − length_reserved ≥ take`. Status induk tetap `available`, tag induk tetap.
- `allocate_and_reserve_rolls`: potongan parsial memakai `_reserve_length` (alokasi SO memuat `reservation_id`, `pending_cut: true`); roll yang sudah punya reservasi panjang hanya dialokasikan dari panjang bebasnya.
- `confirm_cut` + `POST /api/inventory/rolls/{roll_id}/reservations/{rid}/cut` {actual_length, waste}: CAS tarik reservasi + kurangi induk (aktual+waste) dalam satu update; roll anak lahir via `insert_child_roll` (nomor sendiri, tanpa tag, `cut{}` snapshot, journey `cut_pending_tag`); mutasi `roll_cut` + `cut_waste`. `GET /api/inventory/pending-cuts`.
- `rebuild_balance`: panjang yang dipesan masuk bucket status reservasinya (reserved/committed/…), sisa bebas di `available_qty`.
- `release_order_rolls` / `release_order_rolls_partial` / `set_order_rolls_status`: ikut menarik / mengurangi / mengubah status reservasi panjang (tanpa fragmen roll).
- `ship_order_rolls`: reservasi yang belum dipotong dikonfirmasi potong saat dispatch (`cut.mode = at_dispatch`) — jejak tetap ada, tidak ada anak administratif sebelum barang keluar.
- `loading_check_service.start`: ditolak 400 bila SO masih punya reservasi potong (anak belum ada fisik/tag).
- Penjaga: `_reserve_single_roll`, reservasi transfer/interco/retur (`length_reserved` bukan >0), PA create (WM-05) menolak induk berreservasi potong. `insert_child_roll` tidak menyalin `length_reservations/length_reserved/active_movement` dan mengosongkan `earmarked_for` pada potongan non-available (temuan tambahan: potongan transfer mewarisi pegging induk → invariant roll-pegging merah).
- FE: tab **Antrean Potong** (`lp-tab-cuts`, `PendingCutsPanel`, testid `pending-cut-*`) di layar Lokasi & Putaway.

Regression test: `cd backend && python ../audit/iterations/2026-10-02-P02-wm02-reservation/repro_wm02.py` → [after_patch.txt](after_patch.txt) `pass=11 fail=0` (reserve tanpa roll baru, saldo 70/30, konkurensi 2×50 atas bebas 70 → 1 menang, release tanpa fragmen, loading ditolak, potong 100→70+29,5+0,5 waste, potong ulang 404, dispatch at_dispatch).
Legacy/HTTP: `tests/test_allocation_policy_17.py` + `tests/test_roll_pick_and_reallocate.py` 8 passed/1 skipped; `test_core_e8_desk_poc.py` 97/97; `verify_data_integrity.py` PASS 246 · FAIL 0. Agen pengujian independen iterasi 110: 66/66 invariant, tab UI tampil.
Kontrol yang dipertahankan: roll utuh (≤ sisa) tetap dipesan utuh (status reserved); `_split_roll` lama tidak dipanggil alokasi SO lagi (masih dipakai skrip regresi P02).
Data historis/migration dry-run: tidak ada migrasi; roll anak reserved yang lahir sebelum patch tetap apa adanya (sudah "roll" administratif).
Batas pengujian: dispatch memotong otomatis (keputusan: potong dianggap terjadi saat muat); penegakan "tag anak wajib sebelum muat" di gate/loading RFID (P07/P09) belum. Picker `/inventory/rolls/available` masih menampilkan panjang fisik induk (bukan panjang bebas). Swap roll di SO (`sales_orders_extra`) hanya mengenal roll berstatus reserved.
ID siap divalidasi / tertunda: WM-02 in_progress (menunggu SHA). GN-15 tetap terbuka.

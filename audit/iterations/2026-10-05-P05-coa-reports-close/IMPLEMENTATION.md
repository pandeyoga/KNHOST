# IMPLEMENTATION

Commit sumber diuji: `6240190` (checkpoint; patch di atas `7ee284f` yang memuat `1a2c33a` = iterasi 2026-10-04).
ID/fase: P05 — CX-09, FN-04, FN-05, FN-06, FN-09, FN-13, FN-16, IX-08. Lanjutan FN-02 (kunci baris PO dikerjakan ulang). Fitur: cetak label roll anak (QR + Code128), pilih baris PO di form tagihan, laporan Hutang Reimburse.

Reproduksi HEAD sebelum patch: `git worktree add .head_wt HEAD && cd .head_wt/backend && python ../../audit/iterations/2026-10-05-P05-coa-reports-close/repro_p05.py` → [head_before_patch.txt](head_before_patch.txt) `pass=11 fail=18` — kedelapan ID P05 tereproduksi (lihat baris FAIL per ID). Catatan: cek CX-09 "membaca laporan tidak menulis eliminasi" lolos di HEAD hanya karena fixture tidak punya pair JE; bukti statisnya adalah panggilan `sync_ic_eliminations_from_pairs` di `summary`.

## Koreksi FN-02 (penting untuk validator)

Patch 2026-10-04 memakai `items[].line_code` sebagai kunci baris PO. Di data nyata `line_code` adalah **lini produk** (`printing`/`woven`), bukan id baris — fixture lama memakai kode sintetis `L1/L2`, sehingga regresi tidak terlihat. Akibat di `1a2c33a`: dua produk BERBEDA dengan lini sama digabung satu kunci; `evaluate_match` membaca harga/qty produk lain dan `already_billed_map`/konteks tagihan/kontrabon salah menghitung sisa. Bukti: [fn02_line_code_head.txt](fn02_line_code_head.txt) — tagih produk A (PO 10 @100) dinilai "price_variance −88.89% dari 900" (harga produk B), sisa 20 (qty B).
Perbaikan: identitas baris = `items[].line_id` (disimpan permanen oleh `ensure_line_ids` saat konteks/pembuatan tagihan; fallback posisi `L<n>`). Tagihan membawa `po_line_id`; `po_line_code` lama hanya dipakai bila unik per produk. Kontrabon membaca sisa per baris.

## Perubahan

- FN-05: `gl_service.effective_accounts(codes, entity_id)` — global + override entitas (override menang, deterministik). `financial_statement_service._accounts_map(scope)` memakainya; laporan multi-entitas memakai dimensi global. Cash flow ikut.
- FN-06: `create_manual_entry` dan validator pusat `_validate_entry_lines` (semua autopost) memakai resolver yang sama → akun khusus entitas bisa diposting di entitasnya, ditolak di entitas lain; override nonaktif/header menghalangi posting.
- FN-16: `balance_sheet` menetapkan `as_of` efektif sekali (default hari ini) untuk filter DAN label.
- FN-04: arus kas diklasifikasi per jurnal kas: hanya jurnal yang menyentuh akun kas menghasilkan arus; lawan akun menentukan aktivitas. Jurnal nonkas investasi/pendanaan diungkap di `noncash_disclosure` (tampil di tab Arus Kas). Kas & setara kas = akun baku + akun ber-flag `is_cash`/`cash_equivalent`.
- FN-13: `close_period` mengambil kunci atomik per entitas (`period_close_locks`, `_id`=entity) — close bersamaan: satu lolos, sisanya ValueError; kunci basi >10 menit boleh diambil alih.
- FN-09: `void_entry` menjalankan `enforce_closed_period_guard` (izin `period.backdate` dari route), CAS status≠void, void dalam jendela unlock dicatat (`voided_in_unlock` + `je_ids` unlock).
- IX-08: approve/reject = `find_one_and_update` bersyarat `status=pending`; yang kalah `DecisionConflict` → HTTP 409.
- CX-09: eliminasi hanya berlaku bila kedua sisi entitas ada di perimeter; eliminasi tanpa pasangan entitas hanya pada grup penuh. `summary` tidak lagi menyinkronkan eliminasi saat baca (pakai tombol/endpoint sync).
- Fitur: `POST .../cut` & `GET /inventory/cut-children-unverified` membawa `product_name`, `parent_roll_no`, `ref_number` (label); `printCutChildLabels` (QR + Code128 via `jsbarcode`) memakai tata letak label roll yang sudah ada. `GET /cash-advance-settlements/reimburse-payables` (izin accounting.view) + tab "Hutang Reimburse" (umur 0–7/8–14/15–30/>30 hari sejak LPJ disetujui). Form tagihan menampilkan nomor baris PO, lini, harga PO dan sisa per baris.

## Regression

- `cd backend && python ../audit/iterations/2026-10-05-P05-coa-reports-close/repro_p05.py` → [after_patch.txt](after_patch.txt) `pass=29 fail=0`.
- `repro_followup3.py` → [followup3_after.txt](followup3_after.txt) `pass=13 fail=0` (FN-02 lini sama/produk ganda, label, laporan reimburse, 403 gudang).
- Ulang: `repro_followup2.py` 12/12, `repro_p04.py` 7/7, `tests/test_iter112_followup2.py` 6 passed.
- Integritas: PASS 246 · FAIL 2 — keduanya `backorder` pada `KANDA/SO-00001` dari seed ulang lingkungan ini (reservasi SO; tidak disentuh patch ini).

## Batas

- FN-04: klasifikasi berbasis akun lawan pada jurnal kas; jurnal campuran multi-aktivitas dibagi per baris lawan, bukan per dokumen sumber. Belum diverifikasi fixture akuntan (IAS 7/PSAK 2) — perlu review manusia.
- FN-13: kunci per entitas menyerialkan semua close entitas itu (bulan & tahun); reopen/reclose tidak memakai kunci ini (sudah saga sendiri).
- CX-09: kebijakan NCI/kepemilikan parsial belum didukung; eliminasi manual lama tanpa `entity_from/to` hanya berlaku pada konsolidasi grup penuh.
- FN-09: void di periode tertutup kini ditolak; alur "reversal di periode berjalan" belum dibuat (kebijakan buku perlu keputusan pemilik proses).
- FN-02: PO lama dengan produk ganda + tagihan lama tanpa kunci baris tetap dihitung per produk (tidak bisa dipetakan otomatis).
ID: P05 (8 ID) + FN-02 → ready_for_validation pada `6240190`. WM-02, CX-05 → ready_for_validation pada `1a2c33a`.

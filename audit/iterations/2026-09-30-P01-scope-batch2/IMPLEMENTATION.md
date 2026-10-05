# IMPLEMENTATION

Commit sumber diuji: patch di atas `08a9009f18250ea31cecca3ddbe0b7a38561bfe4`, kandidat ter-commit `0076f7ea16ddc93d5b01f480768418464c5c3347`. Diff gabungan P01: [p01_combined.diff](p01_combined.diff).
ID/fase: AX-04, AX-06, CX-02, GN-04, GN-09, GN-10, GN-16, RF-08, RF-09 — P01. Rebaseline tanpa patch: IX-06, CX-10.

Reproduksi HEAD sebelum patch: `cd backend && python ../audit/iterations/2026-09-30-P01-scope-batch2/repro_p01_batch2.py` (fungsi service asli, DB sintetis lokal) → [head_before_patch.txt](head_before_patch.txt) `pass=4 fail=7`:
- AX-04 terbukti: owner A mereservasi roll B; pilihan eksplisit tidak rebuild balance (reserved 50→50).
- AX-06 terbukti: job multi-owner dibuat, 2 tag ter-encode.
- GN-16 terbukti: digest user A memuat notifikasi entitas B; laporan AI terjadwal tanpa `recipient_role=""`.
- RF-08/RF-09 terbukti: sesi A+B tak dapat dipindai (403) dan dapat diselesaikan user A-only.
- TIDAK konklusif di HEAD dengan fixture ini: GN-04 (roll B sudah ter-reserve oleh bug AX-04 → ditolak alasan status), CX-02 (ditolak 400 oleh `_apply_to_order`, bukan validator tujuan), GN-10 (pemanggilan tanda tangan baru → 0 baris). Ketiganya dibuktikan statis: GN-04 `issue_material` tanpa cek owner; CX-02 alokasi otomatis `list_open_orders(customer_id)` tanpa entitas & GET open-orders tanpa scope; GN-10 `entity_id=None` membaca semua order + stok `product_summary` global. GN-09 hanya statis (`_guard_lead_owner` tanpa entitas).

Perubahan dan kontrak lintas caller:
- AX-04 `reserve_rolls_for_wh_transfer`: pilihan eksplisit divalidasi owner/product/status/qty>0/gudang; update bersyarat dimensi sama; konflik di tengah batch melepas HANYA reservasi milik operasi ini (id + reserved_ref); rebuild balance seperti jalur FEFO.
- AX-06 `create_print_job`: validasi scope, satu owner, satu gudang untuk SELURUH roll sebelum encode.
- CX-02 store credit: semua alokasi eksplisit lewat `_validate_allocation_target(customer_id, entity_id)` sebelum mutasi; alokasi otomatis & GET `/store-credit/open-orders` + `/ar-receipts/open-orders` dibatasi entitas.
- GN-04 `issue_material`: roll wajib `owner_entity_id` = entitas sample (selain itu "tidak ditemukan").
- GN-09 CRM: `_guard_lead_owner` + hapus interaksi memakai `guard_doc` entitas; konversi ke customer badan usaha lain ditolak.
- GN-10 POS: router me-resolve scope (`resolve_scope_ids`); order & stok (`inventory_balances.owner_entity_id`) dibatasi scope.
- GN-16: laporan AI terjadwal `recipient_role=""`; digest dibatasi entitas penugasan (+ global tanpa entitas); bootstrap memperbaiki notifikasi `ai_report` lama yang tersiar.
- RF-08/RF-09: sesi & hasil cycle count menyimpan `scope_entity_ids`; reuse sesi hanya scope sama; complete/list/detail/scan wajib scope ⊇ pemilik; backfill bootstrap untuk data lama (turunan owner roll expected).

Regression test: `repro_p01_batch2.py` → 13/13 lulus [after_patch.txt](after_patch.txt). Suite terkait (`test_iter14_wh_transfer_rolls`, `test_iter_sample_pos_extra`, `test_sample_pos_flow`, `test_rnd_samples_qa3`): 5 failed/13 passed/2 skipped IDENTIK di HEAD dan setelah patch (fixture seed lama), bukan regresi.
Kontrol yang dipertahankan: reservasi roll A sendiri; CAS roll; single-warehouse print job; guard owner sales CRM.
Data historis/migration dry-run: backfill cycle count & notifikasi idempotent; job print multi-owner lama tidak dimigrasi (DB sintetis: perlu query `rfid_print_jobs` per owner item di produksi).
Batas pengujian: GN-09 belum diuji dinamis; CX-02 hanya jalur store credit (CX-01/CX-03 = P03); AX-04 belum diuji konkurensi Mongo nyata.
Tertunda: IX-06 (PUT payroll settings masih menulis global — butuh kontrak UI pilih lapisan global/entitas lewat config_resolver), CX-10 (e-sign belum terikat hash versi — `public_verify`/`_attach_esign` masih per doc_type/source_id). Keduanya masih ada di HEAD (statis) → status open.

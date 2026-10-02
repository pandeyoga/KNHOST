# IMPLEMENTATION

Commit sumber diuji: patch di atas `49b177090d57a1d349830c83f7f53c119cb17631` (working tree; SHA kandidat diisi setelah commit platform).
ID/fase: P03 — FN-15, FN-07, FN-08, FN-10, FN-12, CX-01, CX-03, CX-04, CX-05, CX-06, CX-07, CX-08, IX-14, IX-17, AX-02.

Reproduksi HEAD sebelum patch: `cd .head_src/backend && python ../../audit/iterations/2026-10-02-P03-durable-posting/repro_p03.py` → [head_before_patch.txt](head_before_patch.txt) `pass=0 fail=6 crashed=1`: jurnal tidak seimbang / NaN / negatif / dua sisi / akun induk / akun tak dikenal semuanya DITERIMA `_insert_entry` (FN-15); kontrak preflight/status posting belum ada.

Kontrak bersama (`services/gl_service.py`):
- FN-15 `_validate_entry_lines` di `_insert_entry` (semua autopost + manual): finite, ≥0, satu sisi per baris, seimbang ≤0,005, akun ada/aktif/`is_postable`. Baris 0/0 dibuang. DB demo: 0 jurnal lama memakai akun induk/nonaktif.
- `preflight_posting(entity, date)`: periode tertutup ditolak SEBELUM efek bisnis.
- `post_cash_durable(txn)`: jurnal kas + `gl_status` posted|failed + `gl_error` di dokumen kas.

Per temuan:
- FN-07 `routers/cash.py`: create = preflight → kas → jurnal; jurnal gagal → kas dihapus + 409. Void: kas turunan dokumen (`ref_type/ref_id/gl_posted`) atau sudah direkonsiliasi ditolak; klaim `voiding`, jurnal pembalik (`post_cash_void`, idempotent) wajib sukses sebelum status void.
- FN-10 `ar_receipt_service`: preflight sebelum kwitansi/alokasi/deposit; jurnal gagal → `gl_status=failed` (kwitansi & kas) — tidak lagi disembunyikan; `POST /api/ar-receipts/{id}/repost` idempotent.
- FN-08 `bank_service`: rekening baru dengan saldo awal → jurnal Dr Kas/Bank / Cr 3-2900 (satu operasi, rollback rekening bila gagal); ubah saldo awal → jurnal penyesuaian selisih; saldo awal lama tanpa jurnal → 400 (koreksi lewat jurnal manual Keuangan).
- FN-12 `fixed_asset_service.update_asset`: biaya/tanggal/akun aset terkunci setelah jurnal perolehan; umur/nilai sisa terkunci setelah penyusutan; edit nonfinansial tetap.
- CX-01 store credit: alokasi digabung per order, nominal >0, Σ alokasi == amount sebelum mutasi.
- CX-03: preflight + kompensasi `_unapply_receipt` bila jurnal gagal, kunci pelanggan lepas, retry konsisten.
- CX-04 uang muka: saga claim `approved`; kas percobaan gagal dipakai ulang (tanpa kas kedua), status disbursed via CAS.
- CX-05 (keputusan kebijakan yang diterapkan: SATU LPJ per PD): LPJ hanya untuk PD `disbursed` tanpa LPJ aktif; approve mengklaim PD (`settling_stl_id`) sebelum jurnal, rilis bila gagal.
- CX-06/CX-07 bank recon: `_assert_target` tunggal (buku rekening, arah, non-void) untuk manual/split/group; `_link` menggabung txn ganda dan mengklaim kapasitas atomik (CAS `reconciled_amount + alokasi ≤ amount`) dengan kompensasi.
- CX-08 payment plan: `seq` = identitas baris; reschedule memberi seq baru (+`parent_seq`, `line_id`), nomor tampil `display_no`; referensi kwitansi lama tetap ke baris yang sama.
- IX-14 GRN: preflight periode di `_close_preflight`; `complete_task` menyimpan `wms_tasks.gl_posting` posted|failed; `_ensure_gr_posted` mengulang jurnal (idempotent) dan 409 bila masih gagal → baris `failed`, GRN tetap `closing` (tutup ulang setelah pulih).
- IX-17 retur beli: preflight sebelum stok/AP; `ap_adjusted` mencegah AP berkurang dua kali; jurnal gagal → `gl_status=failed` + error; approve ulang melanjutkan posting.
- AX-02 dispatch: surat jalan ditulis SEBELUM tugas `dispatched`; `saga_lock.operation` mencatat shipment/rolls; gagal di tengah → `mark_failed` (kunci terlihat di Kunci Saga); status GL pendapatan di `shipments.gl_status`.

Regression test: `cd backend && python ../audit/iterations/2026-10-02-P03-durable-posting/repro_p03.py` → [after_patch.txt](after_patch.txt) `pass=43 fail=0` (fault injection GL untuk FN-10/CX-03/CX-04/IX-17, periode tertutup sintetis untuk FN-10/IX-14/IX-17).
Legacy: `test_store_credit.py` 2/2; `test_g8_bank_poc.py` 121 PASS · 1 FAIL (invariant global merah oleh residu skrip ini `payment_variance_decisions` — dibersihkan, skrip kini ikut menghapusnya).
HTTP: kas manual via `POST /api/cash-transactions` → gl_status posted + JE; void → jurnal pembalik. Catatan: HEAD sebelum patch tersedia hanya sebagai clone sementara (`.head_src`, dihapus setelah bukti diambil).
Kontrol yang dipertahankan: idempotensi per source, kunci pelanggan KN-B06, guard entitas, toleransi selisih bayar FASE G-3.
Data historis/migration dry-run: tidak ada migrasi. Kas/retur/kwitansi lama tidak punya `gl_status` (diperlakukan tidak diketahui). Rekening seed dengan saldo awal tanpa jurnal tetap (perlu jurnal pembukaan manual).
Batas pengujian: AX-02 hanya statis + kode (tidak ada fixture pick→dispatch dengan injeksi gagal insert shipment); FN-07 void diuji lewat fungsi GL + statis router; tanpa transaksi Mongo — saga/kompensasi, bukan atomik lintas koleksi; CX-05 kelebihan pengeluaran di atas uang muka masih dikredit ke Uang Muka (butuh keputusan akun reimburse).
ID siap divalidasi / tertunda: seluruh ID di atas in_progress (menunggu SHA).

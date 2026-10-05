# IMPLEMENTATION

Commit sumber diuji: patch di atas `5cddfc964ee0b1b84729d13d01a789d31f31bb7d` (memuat iterasi P10). SHA kandidat diisi setelah commit platform.
ID/fase: P11 — CX-13, GN-05, GN-06, GN-07, GN-08, IX-11.

Reproduksi HEAD: worktree `5cddfc9` → `cd .head_wt/backend && python ../../audit/iterations/2026-10-02-P11-mutasi-konversi/repro_p11.py` → [head_before_patch.txt](head_before_patch.txt) `pass=3 fail=12` (draft WO langsung selesai lalu bagian produksi crash; rollback R&D menimpa B → 100; retur beli: roll beda pemilik lolos, dua finalisasi paralel memotong 2×, tanpa child retur; 3 convert paralel → 3 pasangan antar-PT, retry membuat pasangan baru; makloon input-0 diterima dengan nilai fallback). Yang sudah benar di HEAD: cancel sesudah convert ditolak (`_assert_open`), receive makloon paralel in-process sudah 1 sukses (claim lama).

## Perubahan

- **GN-06 / IX-11 — `services/production_service.py`**
  - Kontrak bersama `eligible_material_q`: owner + gudang + `available` + `length_remaining>0` + **`inspection.hold.held != true`**; ketersediaan = panjang BEBAS (sisa − `length_reserved`). Dipakai precheck, rencana bahan dan CAS konsumsi.
  - Resep dibekukan di WO (`bom_components`, `bom_version_at`) saat dibuat; release/complete/detail memakai resep beku, bukan BOM terbaru. WO lama tanpa snapshot → dari `material_plan` awal.
  - Draft tidak bisa langsung complete (400 "rilis dulu") — **default teknis**, menunggu konfirmasi pemilik proses. UI: tombol Selesaikan hanya untuk WO dirilis.
  - Complete: `atomic_claim.claim(status=released)` → konsumsi CAS per roll (`$expr` panjang bebas ≥ ambil, pipeline update) dengan movement ber-`operation_id` → output (idempoten: dicari `acquired.via=production_output, ref_id=wo`) → JE (idempoten per WO) → `finish_set`. Tahap durable di `completion {op_id, stage, consumed, roll_id}`.
  - Kekurangan di tengah konsumsi (balapan/hold) → `reverse_operation(op_id)` membalik HANYA kontribusi operasi ini (`$inc`, movement ditandai `reversed` + movement `production_consume_reversal`), kunci dilepas, 409 tanpa efek parsial. Crash lain → `mark_failed` (terlihat di Kunci Saga); retry setelah admin melepas kunci melanjutkan dari tahap tersimpan (stage `consuming` → kontribusi lama dibalik dulu).
  - Release/cancel memakai CAS status + tanpa kunci (cancel saat complete berjalan → 409).
- **GN-05 — `services/rnd_sample_service.py`**: rollback GL gagal kini `$inc +qty` (status `consumed` dikembalikan), dijalankan hanya bila movement operasi ini berhasil dihapus → idempoten, tidak menimpa pemakaian lain.
- **GN-07 — `services/purchase_return_service.py`**: `_consume_available_rolls` + `_consume_specific_rolls` diganti satu jalur `_consume_return_rolls`: roll pilihan wajib milik badan usaha retur & produk baris (else 400 sebelum mutasi), status `available|quarantine`, qty dikonversi ke satuan dasar (`to_base_qty`), CAS per roll atas panjang bebas. Penuh → roll itu `returned_supplier`; sebagian → **roll anak** `returned_supplier` (nomor roll sendiri, tanpa tag RFID induk, `parent_roll_id`), induk berkurang; movement `return_out` menunjuk potongan. applied ≠ requested → kontribusi dibalik (`_undo_return_effects`) + 400. Finalisasi stok diklaim (`purchase_return_finalize_stock`, prasyarat `stock_adjusted != true`). Reversal yang ada tetap kompatibel (potongan anak kembali `available`). `ship_to_supplier` mengarantina roll dengan CAS + cek pemilik.
- **GN-08 — `services/internal_request_service.py`**: `convert` mengklaim permintaan (`submitted`, tanpa kunci) sebelum membuat pasangan; kunci logis `source_request_id` → retry memakai pasangan yang sudah lahir. IntercoError → kunci dilepas; error lain → `mark_failed`. Reject/cancel ber-CAS (status terbuka + tanpa kunci).
- **CX-13 — `services/makloon_order_service.py`**: klaim berprasyarat `steps.$elemMatch{seq, status: issued}`; snapshot HASIL klaim menjadi dasar perhitungan (kiriman sebagian berubah → 409). Input sudah 0 tanpa progres sah → 409 (tidak lagi fallback nilai step). Progres durable `steps[].receive_progress {op_id, consumed, bill_id, lots, byproduct_done}` → retry tidak mengonsumsi/menagih/membuat roll ulang (tagihan juga dicari via `receive_op_id`). Tulisan akhir `update_one` milik pemegang `saga_lock.token` (bukan `replace_one` + release buta). `atomic_claim.release(..., token)` kini mendukung pelepasan milik-token.
- `routers/saga_locks.py`: `mfg_work_orders`, `internal_requests` ditambahkan ke koleksi berkunci.
- UI produksi: pesan galat 409 berbentuk objek ditampilkan sebagai teks.

## Regression

- `repro_p11.py` → [after_patch.txt](after_patch.txt) `pass=21 fail=0`.

## Batas

- IX-11: jalur override/rework untuk bahan tertahan BELUM dibuat — perlu keputusan pemilik (hak, alasan, cakupan qty, referensi inspeksi).
- GN-06: kebijakan "draft wajib dirilis" dan yield/waste aktual (output = planned_qty) belum diubah; perlu keputusan pemilik proses.
- GN-07: identitas anak retur = nomor roll baru (barcode); tag RFID fisik baru belum otomatis dicetak.
- CX-13/GN-06: jendela crash antara CAS roll dan insert movement masih ada (tanpa transaksi Mongo — keputusan §7 2026-09); kunci tetap tertinggal dan terlihat di Kunci Saga.
- Konkurensi diuji in-process (asyncio.gather), bukan uji beban multi-proses.
- Data historis: WO lama tanpa `bom_components` memakai `material_plan` awal; tidak ada migrasi data.

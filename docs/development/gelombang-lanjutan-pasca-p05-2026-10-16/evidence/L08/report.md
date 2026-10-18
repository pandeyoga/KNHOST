# Laporan Fase L08 — status `in_progress` (2026-10-17, agent E1)

Belum ber-SHA GitHub. Pending KLR-08 (hangtag hilang / kain sudah dipotong) dan KLR-09 (batas 21 hari dihitung sampai kapan) memblok LN-083; tidak diasumsikan.

## Navigasi aktual
- Retur Penjualan (`?view=sales-returns`) → Buat Return → pilih SO (`return-order-select`) → baris produk otomatis dari Surat Jalan (`item-product-<i>`, satuan `item-unit-<i>`), centang roll terkirim (`item-roll-<rollId>`, menampilkan no. roll · SJ · sisa) → qty terisi dari roll → Buat Return.

## LN-080 — form retur dari barang terkirim (T01, T02 selesai lokal)
- Sebelum: baris retur diketik manual (ID produk mentah); batas retur per produk memakai qty terkirim, tetapi jatuh ke qty TERJUAL bila belum ada pengiriman; roll yang diklaim tidak tersimpan (skema membuang `roll_ids`); dua klaim paralel bisa lolos cek batas bersamaan.
- Sesudah:
  - `GET /api/sales-returns/returnable?order_id=` (izin `sales_return.create`, cakupan badan usaha): roll per SJ (`shipments.rolls`) dengan no. roll, SJ, nama produk, SKU, warna, qty kirim, sudah diretur, sisa; ringkasan per produk.
  - `create_return` memakai `return_rolls_service.assert_shipped_items`: produk wajib ada di SJ SO ini, roll wajib roll terkirim produk itu, klaim per roll (`roll_qtys`, kosong = seluruh panjang) dan kumulatif per produk ≤ terkirim. SO tanpa SJ → 400.
  - Kunci per SO (`return_create_locks`, TTL 60 detik) membungkus cek + simpan → klaim paralel: hanya satu yang tersimpan, sisanya 400 jelas.
  - Skema `SalesReturnItem` += `roll_ids`, `roll_qtys`. Retur lama tidak dimigrasi; approve tetap memakai cek lama.
  - UI: tidak ada lagi "Tambah Item" bebas / input ID produk.
- Perbaikan review (iteration_206): cek akses badan usaha saat membuat retur; qty tanpa `roll_qtys` dibagi ke roll terpilih sesuai SISA (bukan panjang kirim penuh) dan disimpan; roll sama di dua baris dijumlah dulu; qty harus = jumlah klaim per roll.
- T03 (sesi 2026-10-17 lanjutan): kewajiban bukti per tahap — 4 setting `returns.evidence_required_{submit,approve,inspect,settle}` (grup baru "Retur Penjualan", bawaan MATI = bukti boleh dilengkapi kemudian, scope global/entitas).
  - API: `services/return_evidence_service.py`; router menolak 400 "Bukti foto wajib sebelum retur …" pada submit/approve/inspect-complete/settle bila tahap itu wajib & lampiran 0; `submit_now` saat buat ditolak bila tahap ajukan wajib (simpan draf dulu). `GET /api/sales-returns/meta/evidence-policy`; detail membawa `evidence {required, count, missing_for}`.
  - UI: form Buat Retur punya input foto (`return-photo-input`) — dengan foto: simpan draf → unggah → ajukan; petunjuk wajib (`return-photo-required-hint`). Detail menampilkan `return-evidence-missing` bila tahap berikut masih butuh bukti.
- T04: status & kategori kini **saringan dropdown** (`return-status-filter`, `return-type-filter`), bukan deretan tab. `GET /status-counts` menerima `return_type`, `line`, `q` → kartu total memakai cakupan yang SAMA dengan daftar; label cakupan `return-stats-scope`; tiap kartu menjelaskan rumusnya (Diproses = status 3+4+5, Selesai = refund+store credit+nego tanpa ditolak/batal); `return-list-count` = jumlah daftar sesuai status terpilih.

## LN-082 — identitas roll retur (implementasi lokal, belum ber-SHA)
- Sebelum: penyelesaian retur selalu membuat roll BARU `RTN-NNNNN` per baris (identitas, tag dan riwayat roll asal terputus); nomor potongan `induk-N` dihitung dari jumlah dokumen (tidak atomik); tidak ada larangan kirim ulang ke pelanggan asal.
- Sesudah (`services/return_identity_service.py`, dipanggil `_restock_returned_items` untuk baris ber-`roll_ids`):
  - **Roll utuh** (status `delivered`, klaim = panjang terkirim) diaktifkan lagi dengan **id, `roll_no` dan tag yang sama** → karantina; `length_initial` (bruto) tetap, `length_remaining` = qty aktual QC. `return_history[]` menyimpan SO/SJ, pelanggan, qty bruto/klaim/aktual, grade lama→baru; snapshot `return_restore` dipakai reversal untuk mengembalikan roll ke "di pelanggan" (bukan dihapus).
  - **Klaim sebagian** → child `<nomor induk>-N` (`parent_roll_id`, `root_roll_id`, tanpa tag), riwayat diwarisi.
  - Inspeksi menerima `roll_actuals {roll_id: qty}` (UI: baris "Qty aktual per roll" di panel inspeksi).
  - `roll_service.child_roll_no` memakai sequence atomik per induk (`number_sequences` doc_type `ROLL_CHILD:<induk>`), berlaku untuk semua jalur potong.
  - `returned_from_customer_ids` ikut tersalin ke setiap potongan (semua jalur split menyalin dokumen induk). Setting `returns.block_resend_to_origin_customer` (bawaan AKTIF, izin ubah `sales_return.policy` — aktivitas baru di custom role, default admin & manager): alokasi otomatis (`_available_rolls_for_order`) melewati roll itu untuk pelanggan asal; pilihan roll manual (`reserve_roll_mode_item`) → 409.
- Migrasi: tidak ada. Baris retur lama tanpa `roll_ids` tetap memakai jalur roll RTN baru.

## LN-081, LN-083
- LN-081 belum dikerjakan. LN-083 terblokir KLR-08/KLR-09.

## Bukti
- `backend/tests/test_l08_evidence_identity.py` 10/10 (T03 bukti opsional/wajib + unggah lalu ajukan; T04 hitungan = daftar untuk 4 saringan tipe; LN-082 roll utuh tetap id/nomor + riwayat + reversal memulihkan; klaim sebagian → child bernomor induk; 4 potongan paralel → nomor -1..-4 unik & panjang terjaga; blokir pelanggan asal + 403 untuk sales mengubah toggle).
- `test_l08_returnable_rolls.py` 3/3 & `_extra.py` 16/16 (ID SO kini dicari dari nomor, bukan id seed lama).
- `backend/tests/test_l08_returnable_rolls.py` 2/2 (roll asing & SO belum terkirim ditolak; 4 klaim paralel → 1 tersimpan, sisa roll tepat).

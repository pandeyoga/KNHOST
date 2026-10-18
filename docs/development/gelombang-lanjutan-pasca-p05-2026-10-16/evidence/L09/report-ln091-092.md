# LN-091 / LN-092 — Refund, potong tagihan, cutloss & diskon (in_progress, 2026-10-18)

## LN-091 (sebagian: aturan "potong tagihan dulu" sudah disepakati; KLR-10 masih pending)
- Settle `refund` / `store_credit`: nota kredit lebih dulu mengurangi tagihan **SO asal** (`ar_applied = min(kredit, sisa tagihan)`). Hanya kelebihannya (`excess_amount`) yang dibayar tunai atau masuk saldo.
  - Contoh: kredit 30, tagihan 20 → potong 20, saldo/refund 10 (bukan 30).
  - Jurnal: Dr Pendapatan (+PPN) / Cr Piutang 20 + Cr Kas atau Saldo kredit 10, seimbang.
  - Sebelumnya refund pada SO tempo mengkredit piutang penuh, sehingga kelebihannya menggantung.
- Pengaturan `returns.bill_first` (bawaan true). Cakupan = SO asal sebagai **ASUMSI KLR-10** (`credit_notes.bill_scope = source_order`).
- Klaim atomik settle yang sudah ada (KN-B02) tetap menjaga retry: nota kredit, kas, dan saldo tidak dobel.
- Belum: T02 (penurunan grade → impairment terpisah) belum dibangun.

## LN-092 (simulasi saja — posting dikunci, sesuai T03)
- `POST /api/sales-returns/cutloss/simulate`: contoh resmi 120 yd, cacat yd 46–60. Ketiga skenario KLR-01 tampil berdampingan:
  - hanya cacat: kembali 15, customer simpan 105
  - cacat + sisi pendek: kembali 60, 45 masuk stok
  - seluruh roll: 120
  - Semua skenario terekonsiliasi. `selected=null` dan `posting_locked=true` selama KLR-01/02 pending.
- `POST /api/sales-returns/discount/simulate`: nilai diskon dihitung, gerak stok 0.
- Settle `nego` (diskon tanpa barang kembali) **wajib pengecualian QC `discount_no_goods` yang disetujui + foto** selama `returns.discount_mode = pending`.
- Asumsi configurable di panel Kebijakan Retur: `cutloss_return_part`, `cutloss_value_basis`, `discount_mode`.

## LN-083 lanjutan — kondisi & pengecualian
- Form retur: centang "Hangtag hilang" / "Kain sudah dipotong customer". Nilainya tersimpan di `condition_flags` dan dievaluasi di kelayakan (KLR-08 pending).
- Pengecualian `POST /api/sales-returns/{id}/exceptions` (alasan ≥10 karakter + ≥1 foto dari lampiran retur) dan `…/decide` (izin `sales_return.approve`; pengaju tidak boleh memutus sendiri; penolakan wajib alasan; diaudit). Potret kelayakan disimpan; tanggal histori tidak diubah.
- Gerbang settle: KLR-08 pending tanpa pengecualian "kondisi" → 409; di luar batas tanpa pengecualian "batas waktu" → 409.

## Uji
- `tests/test_ln091_092_returns_exceptions.py` 5/5. Testing agent iteration_229: backend 27/27, UI 100%.

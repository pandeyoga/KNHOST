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

## Update 2026-10-19 (sesi lanjutan) — LN-092 cutloss & diskon final (KLR-01/02/06/07)
- **Cutloss:** `POST /api/sales-returns/{id}/cutloss` {product_id, defect_yard, roll_id?, note} — izin baru `sales_return.record_cutloss` (admin, manager, md, md_quality). Qty cacat dalam **yard**; produk ber-satuan dasar kg dikonversi otomatis lewat master UoM (`to_base_qty`). Tidak boleh melebihi qty retur.
- **Nilai:** `GET /api/sales-returns/{id}/compensation` → harga **transaksi awal neto** (line_total ÷ qty dasar, dikurangi diskon header) × qty cacat. `POST /api/sales-returns/{id}/compensation` {lines:[{kind: cutloss|discount, product_id, qty, amount, evidence_ids}], note} — izin baru `sales_return.decide_compensation` (admin, manager, **finance**). Diskon = nominal rupiah per item untuk qty cacat (qty ≤ qty retur). `DELETE` = batalkan keputusan.
- **Penyelesaian:** outcome `nego` wajib keputusan Finance; Credit Note memakai nilai keputusan (`credit_amount`), tanpa gerak stok/COGS. Diskon dengan bukti foto/video boleh diselesaikan dari status `approved` tanpa QC fisik (transisi `approved → nego_settled`, dijaga router).
- Setelan asumsi `cutloss_return_part`, `cutloss_value_basis`, `discount_mode` dihapus; simulator menampilkan aturan final (120 yd, cacat 46–60 → customer 45 + 60 yd, kompensasi 15 yd).
- UI: panel `return-compensation-panel` di detail retur (cutloss-record-form, cutloss-defect-yard, cutloss-record-submit, compensation-decide-form, discount-qty-<pid>, discount-amount-<pid>, compensation-evidence-<att>, compensation-note, compensation-decide-submit, compensation-decided, compensation-settle-photo, compensation-revoke).
- **Uji:** `test_ln092_cutloss_simulation_final_rule`, `test_ln092_cutloss_recorded_by_md_valued_by_finance_and_settled_as_nego`, `test_ln092_discount_from_photo_without_goods` (lulus).
- **Tidak diasumsikan:** persetujuan customer atas bentuk potongan (owner tidak menyebut); pemecahan fisik roll di stok tidak dimodelkan (barang tetap di customer).

## Update 2026-10-19 (sesi lanjutan) — LN-091 KLR-10 & KLR-11
- **KLR-10:** cakupan potong tagihan tetap **hanya SO asal**; utang SO lain tidak dipotong. Untuk penyelesaian `nego` (cutloss/diskon) customer memilih `payout`: `store_credit` (saldo) | `refund` (kas) | "" (pengurang piutang SO asal). Refund/saldo memakai jalur Credit Note + buku kas / ledger saldo existing (tagihan SO asal yang masih terbuka dipotong dulu, sisanya dibayar/jadi saldo). UI: `settle-nego-payout` (`settle-payout-store_credit|refund|ar`) di modal Selesaikan; `compensation-payout` di penyelesaian diskon foto.
- **KLR-11:** `PUT /api/sales-returns/{id}/logistics` {costs:[{type: customer_return|qc_trip|replacement_shipping, bearer: company|customer, amount, note}]} (izin `sales_return.update`, terkunci setelah retur selesai). Total per penanggung disimpan; snapshot ikut ke `decision.logistics_costs` saat settle. UI `return-logistics-panel` (logistics-bearer-<type>, logistics-amount-<type>, logistics-note-<type>, logistics-save, logistics-totals).
- **Tidak diasumsikan:** posting otomatis biaya ongkir (penagihan ke customer / beban perusahaan) — dicatat sebagai keputusan per kasus; penagihan/pembebanan lewat modul tagihan/biaya existing.
- **Uji:** `test_ln091_klr10_nego_payout_choice_saldo_with_source_paid`, `test_ln091_klr11_logistics_bearer_per_case` (lulus).

## LN-093 (KLR-09) — catatan
- Retur internal Sukacita → CST tidak memiliki batas waktu tersendiri di kode; batas yang berlaku: customer (tanggal pengajuan, LN-083) dan supplier (sampai klaim dikirim). Pada disposisi CST, lewat-batas supplier dinilai pada hari keputusan "Retur ke supplier" (= klaim dibuat/dikirim, `claim_date` tampil di baris disposisi); retur beli menyimpan `claim_window_check` berdasar tanggal pengajuan klaim.

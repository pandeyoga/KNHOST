// UAT 24 Okt (audit UI tahap 2) — G1-07/G1-26: label Indonesia untuk kode sumber jurnal (source_type) & asal roll
// (acquired.via). Dulu disalin di GeneralLedger.jsx saja; panel "Kenapa berselisih?" mencetak kode mentah.
// Padanan backend: gl_service.ROLL_ORIGIN_LABEL / JOURNAL_SOURCE_LABEL (kalimat dugaan penyebab).

export const SOURCE_LABELS = {
  manual: "Manual", sales_order: "Penjualan", cash_transaction: "Kas", reversal: "Pembalik",
  shipment_revenue: "Pendapatan Kirim", shipment_cogs: "HPP Kirim", sales_cogs: "HPP Penjualan",
  sales_invoice: "Faktur Penjualan", sales_return: "Retur Penjualan", sales_return_reversal: "Pembalik Retur Jual",
  purchase_order: "Pembelian (PO)", po: "Pembelian (PO)", purchase: "Pembelian", purchase_return: "Retur Pembelian",
  goods_receipt: "Penerimaan Barang", vendor_bill: "Tagihan Supplier", vendor_bill_reversal: "Pembalik Tagihan Supplier",
  landed_cost: "Biaya Masuk", contra_bon_deduction: "Potongan Kontrabon", ap_variance_writeoff: "Hapus Selisih Hutang",
  interco_transaction: "Antar-PT", interco: "Antar-PT", interco_return: "Retur Antar-PT",
  interco_settlement: "Pelunasan Antar-PT", interco_loan: "Pinjaman Antar-PT", interco_loan_repayment: "Cicilan Pinjaman Antar-PT",
  inter_company_transfer: "Transfer Antar-PT",
  cash_transaction_void: "Anulir Kas", cash_transaction_reversal: "Pembalik Kas", petty_cash_settlement: "LPJ Kas Kecil",
  bank_holding_alloc: "Alokasi Dana Titipan", bank_opening_adjustment: "Penyesuaian Saldo Awal Bank",
  ar_receipt_deposit: "Penerimaan Piutang", ar_receipt_deposit_void: "Anulir Penerimaan Piutang",
  advance_reclass: "Reklas Uang Muka", advance_reclass_reversal: "Pembalik Reklas Uang Muka",
  payment_variance_alloc: "Alokasi Selisih Bayar", payment_variance_reversal: "Pembalik Selisih Bayar",
  payment_variance_writeoff: "Hapus Selisih Bayar", amendment_credit_note: "Nota Kredit Koreksi",
  store_credit_adjust: "Penyesuaian Saldo Kredit", store_credit_redeem: "Pemakaian Saldo Kredit",
  penalty: "Denda", penalty_payment: "Pembayaran Denda", penalty_reversal: "Pembalik Denda",
  inventory_opening: "Saldo Awal Persediaan", inventory_writeoff: "Hapus Persediaan", cycle_count_variance: "Selisih Stok Opname",
  return_cutloss: "Rugi Retur (cut-loss)", return_grade_impairment: "Penurunan Grade Retur", return_logistics: "Ongkir Retur",
  repair_order: "Perbaikan", production_output: "Hasil Produksi", rnd_sample_issue: "Pemakaian Sample R&D",
  subcon_issue: "Kirim ke Makloon", subcon_issue_reversal: "Pembalik Kirim Makloon", subcon_receipt: "Terima dari Makloon",
  subcon_service: "Jasa Makloon", subcon_service_unabsorbed: "Jasa Makloon Tak Terserap",
  makloon_claim: "Klaim Makloon", makloon_material_loss: "Susut Bahan Makloon",
  payroll_run: "Penggajian", payroll_pay: "Pembayaran Gaji", incentive_accrual: "Akrual Insentif", incentive_accrual_adj: "Koreksi Akrual Insentif",
  fixed_asset_acquisition: "Perolehan Aset", fixed_asset_depreciation: "Penyusutan Aset", fixed_asset_disposal: "Pelepasan Aset",
  fixed_asset_transfer: "Mutasi Aset", fixed_asset_transfer_settlement: "Pelunasan Mutasi Aset",
  closing: "Tutup Buku", suspense_reclass: "Reklas Akun Penampung", finance_case: "Kasus Keuangan",
  manual_void: "Anulir Manual", "tanpa sumber": "Tanpa sumber",
};

/** Asal roll (`acquired.via` / `origin_type`) → kalimat Indonesia. */
export const ORIGIN_LABELS = {
  initial: "Saldo awal", inbound: "Barang masuk (penerimaan PO)", transfer: "Transfer antar-PT",
  production_output: "Hasil produksi", subcon_receipt: "Terima dari makloon",
  subcon_receipt_byproduct: "Hasil sampingan makloon", return: "Retur penjualan",
  cycle_count_found: "Temuan stock opname", cut: "Hasil potong roll", split: "Pecahan roll",
  pod_auto: "Konfirmasi terima otomatis", spesifikasi: "Spesifikasi", sample: "Sample",
  "tidak tercatat": "Asal tidak tercatat",
};

const humanize = (code) => {
  const s = String(code || "").replace(/_/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "—";
};

export const sourceLabel = (code) => SOURCE_LABELS[code] || humanize(code);
export const originLabel = (code) => ORIGIN_LABELS[code] || humanize(code);

/** Status roll yang ikut dinilai di rekonsiliasi persediaan (catatan kaki). */
export const ROLL_STATUS_LABELS = {
  available: "tersedia", reserved: "dipesan", committed: "terikat", picked: "diambil", packed: "dikemas",
  quarantine: "karantina", hold: "ditahan",
};

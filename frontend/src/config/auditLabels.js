// X-1 / X-2 (audit 2026-09-02) — label Indonesia untuk kunci mentah modul izin & aksi audit.
// Kunci yang belum terpetakan jatuh ke pemformatan generik (snake_case → "Kata Kata").

export const MODULE_LABEL = {
  product: "Produk", customer: "Pelanggan", warehouse: "Gudang", uom: "Satuan (UOM)", template: "Template Dokumen",
  order: "Pesanan Penjualan", sales: "Penjualan", sales_admin: "Meja Admin Sales", invoice: "Invoice",
  ar_receipt: "Penerimaan AR", payment_plan: "Rencana Pembayaran", penalty: "Denda", tax: "Pajak", tax_invoice: "Faktur Pajak",
  input_tax: "PPN Masukan", document: "Dokumen", document_delivery: "Pengiriman Dokumen", pdf_template: "Template PDF",
  inventory: "Persediaan", wms: "WMS / Gudang", cycle_count: "Stock Opname", transfer: "Transfer Antar Gudang",
  logistics: "Logistik / Pengiriman", vehicle_log: "Log Kendaraan", label: "Label RFID", inspection: "Inspeksi QC",
  purchase_order: "Purchase Order", purchase_requisition: "Permintaan Pembelian", purchase_return: "Retur Pembelian",
  rfq: "RFQ / Penawaran", supplier: "Supplier", supplier_contract: "Kontrak Supplier", supplier_item: "Item Supplier",
  vendor_bill: "Tagihan Supplier", contra_bon: "Kontrabon", landed_cost: "Biaya Masuk (landed cost)", makloon: "Makloon", makloon_order: "Order Makloon",
  process_recipe: "Resep Proses", production: "Produksi", rnd: "R&D", design_request: "Permintaan Desain", designer: "Desainer",
  color: "Warna / Labdip", sales_return: "Retur Penjualan", internal_request: "Permintaan Internal", cash: "Kas",
  cash_advance: "Kasbon", cash_settlement: "Pertanggungjawaban Kasbon", finance: "Keuangan", finance_case: "Kasus Keuangan",
  finance_amendment: "Amandemen Keuangan", accounting: "Akuntansi / GL", period: "Periode Akuntansi", budget: "Anggaran",
  fixed_asset: "Aset Tetap", interco: "Antar-Badan Usaha", interco_finance: "Keuangan Antar-BU", entity: "Badan Usaha",
  price_approval: "Persetujuan Harga", pricelist: "Daftar Harga", approval: "Persetujuan", permission: "Matriks Izin",
  user: "Pengguna", settings: "Pengaturan", scheduler: "Penjadwal", audit: "Audit", reports: "Laporan", report: "Laporan",
  hr: "SDM (HRD)", esign: "Tanda Tangan Elektronik", pegging: "Alokasi Stok", driver: "Sopir",
  // UAT 24 Okt (audit UI tahap 2) — G0-03/G0-16: modul izin yang belum berlabel (pesan 403 & matriks izin).
  data_export: "Ekspor Data", design_ownership: "Kepemilikan Desain", gl_mapping: "Pemetaan Akun GL",
  grade_master: "Master Grade Mutu", interco_price: "Harga Antar-BU", marketing: "Pemasaran", md_quality: "Mutu Barang (MD)",
  od_fulfillment: "Pemenuhan Pesanan Khusus", od_pricing: "Harga Pesanan Khusus", payment_variance: "Selisih Bayar",
  qc: "QC", repair_order: "Order Perbaikan", sample_order: "Pesanan Sample", special_order: "Pesanan Khusus",
};

export const ACTION_LABEL = {
  view: "Lihat", create: "Buat", update: "Ubah", delete: "Hapus", import: "Impor", export: "Ekspor", print: "Cetak",
  approve: "Setujui", reject: "Tolak", verify: "Verifikasi", confirm: "Konfirmasi", cancel: "Batalkan", void: "Batalkan (void)",
  manage: "Kelola", configure: "Konfigurasi", submit: "Ajukan", complete: "Selesaikan", assign: "Tugaskan", dispatch: "Dispatch",
  ship: "Kirim", deliver: "Serahkan", receive: "Terima", scan: "Scan", adjust: "Penyesuaian", pay: "Bayar", settle: "Lunasi",
  disburse: "Cairkan", claim: "Klaim", claim_approve: "Setujui Klaim", waive: "Bebaskan", backdate: "Tanggal Mundur",
  release: "Lepaskan", reopen: "Buka Kembali", unlock: "Buka Kunci", sign: "Tandatangani", send: "Kirim", run: "Jalankan",
  generate: "Hasilkan", issue: "Terbitkan", inspect: "Inspeksi", assess: "Nilai", award: "Tetapkan Pemenang", decide: "Putuskan",
  propose: "Usulkan", resolve: "Selesaikan Kasus", return: "Retur", replace: "Ganti", convert: "Konversi", dispose: "Hapus Buku",
  manage_bom: "Kelola BOM", manage_org: "Kelola Organisasi", manage_attendance: "Kelola Absensi", manage_payroll: "Kelola Gaji",
  manage_settings: "Kelola Pengaturan", policy: "Atur Kebijakan", view_pii: "Lihat Data Pribadi", approve_count: "Setujui Opname",
  // UAT 24 Okt (audit UI tahap 2) — G0-03/G0-16: aksi izin yang belum berlabel.
  activate: "Aktifkan", admin: "Administrasi", approve_loss: "Setujui Susut", approve_payment: "Setujui Pembayaran",
  cutting_config: "Atur Pemotongan", cutting_receive: "Terima Hasil Potong", decide_compensation: "Putuskan Kompensasi",
  decide_rolls: "Putuskan per Roll", hold: "Tahan", lock: "Kunci", override: "Kecualikan Aturan", paper_check: "Cek Kertas",
  pic_decide: "Keputusan PIC", random_check: "Cek Acak", realize: "Realisasikan", record_cutloss: "Catat Potongan Cacat",
  record_loss: "Catat Susut", release_hold: "Lepas Tahanan", release_unpaid: "Lepas Sebelum Lunas",
  review_credit_note: "Tinjau Nota Kredit", set: "Atur", set_price: "Tetapkan Harga", exact_cut: "Potong Roll",
  untagged_override: "Izinkan Roll Tanpa Tag", override_fail: "Kecualikan Hasil Gagal", tax: "Pajak", report: "Laporan",
  invoice: "Tagihkan", pegging: "Alokasi Stok", cycle_count: "Stock Opname",
};

// Aksi audit (audit_logs.action). Awalan modul dipakai untuk kunci yang belum terdaftar.
export const AUDIT_ACTION_LABEL = {
  login: "Masuk", logout: "Keluar", CREATE: "Dibuat", APPROVE: "Disetujui", COMPLETE: "Diselesaikan",
  ESCALATE: "Dieskalasi", RESOLVE_ESCALATION: "Eskalasi diselesaikan",
  order_created: "Pesanan dibuat", order_verified: "Pesanan diverifikasi", order_confirmed: "Pesanan dikonfirmasi",
  order_auto_approved: "Pesanan disetujui otomatis", sales_order_verified: "Pesanan diverifikasi",
  outbound_tasks_auto_created: "Tugas outbound dibuat otomatis", backorder_auto_fulfilled: "Backorder terpenuhi otomatis",
  inbound_scan_receive: "Scan penerimaan barang", inbound_completed: "Penerimaan selesai", restock_requested: "Permintaan restock",
  roll_grade_changed: "Grade roll diubah", qc_decision: "Keputusan QC",
  po_created: "PO dibuat", vendor_bill_created: "Tagihan supplier dibuat", vendor_bill_posted: "Tagihan supplier diposting",
  vendor_bill_payment: "Pembayaran tagihan supplier", supplier_contract_created: "Kontrak supplier dibuat",
  supplier_invoice_exchange_set: "Tukar faktur ditetapkan", purchase_return_created: "Retur pembelian dibuat",
  contra_bon_created: "Kontrabon dibuat", contra_bon_submitted: "Kontrabon diajukan", contra_bon_verified: "Kontrabon diverifikasi",
  contra_bon_approved: "Kontrabon disetujui", contra_bon_scheduled: "Kontrabon dijadwalkan", contra_bon_paid: "Kontrabon dibayar",
  contra_bon_deduction_added: "Potongan kontrabon ditambah",
  sales_return_created: "Retur penjualan dibuat", sales_return_approved: "Retur penjualan disetujui",
  sales_return_inspect_started: "Inspeksi retur dimulai", sales_return_inspected: "Retur diinspeksi",
  sales_return_quarantine_released: "Karantina retur dilepas", sales_return_settled: "Retur penjualan diselesaikan",
  interco_transaction_created: "Transaksi antar-BU dibuat", interco_transaction_invoiced: "Transaksi antar-BU ditagihkan",
  interco_return_created: "Retur antar-BU dibuat", interco_return_approved: "Retur antar-BU disetujui",
  interco_return_task_created: "Tugas retur antar-BU dibuat", interco_warehouse_task_created: "Tugas gudang antar-BU dibuat",
  inter_company_transfer_executed: "Transfer antar-BU dijalankan",
  internal_request_created: "Permintaan internal dibuat", internal_request_converted: "Permintaan internal dikonversi",
  logistics_create: "Pengiriman dibuat", logistics_update: "Pengiriman diubah", logistics_status: "Status pengiriman diubah",
  logistics_photo: "Foto pengiriman diunggah", logistics_photo_delete: "Foto pengiriman dihapus", logistics_position: "Posisi pengiriman dicatat",
  logistics_position_delete: "Posisi pengiriman dihapus", logistics_route: "Urutan rute sopir disusun",
  design_gallery_ai_illustrate: "Ilustrasi AI galeri dibuat", design_gallery_ai_comment: "Komentar ilustrasi AI",
  design_gallery_ai_comment_delete: "Komentar ilustrasi AI dihapus", design_gallery_autotag: "Auto-tag AI galeri",
  integrations_update: "Integrasi AI diubah", integrations_gemini_test: "Uji koneksi Gemini",
  document_generated: "Dokumen dihasilkan", journal_entry_created: "Jurnal dibuat", gl_posted: "Diposting ke GL",
  // UAT 24 Okt (audit UI tahap 2) — G0-16: kunci yang tampil di Jejak Audit dengan humanize Inggris
  // ("Reservation Expired", "Login") atau tak cocok dengan pola <sumber daya>_<kata kerja> di bawah.
  reservation_expired: "Reservasi kedaluwarsa", reservation_released: "Reservasi dilepas", reservation_created: "Reservasi dibuat",
  create: "Dibuat", update: "Diubah", delete: "Dihapus", activate: "Diaktifkan", import: "Impor data",
  earmark: "Stok ditandai untuk pesanan", unearmark: "Penandaan stok dilepas",
  "export.create": "Ekspor dibuat", "export.download": "Ekspor diunduh", "export.download_denied": "Unduhan ekspor ditolak",
  "esign.sign": "Dokumen ditandatangani", "delivery.whatsapp": "Dokumen dikirim lewat WhatsApp",
  "hr.payroll.run": "Penggajian dijalankan", "hr.payroll.run_post_gl": "Penggajian diposting ke GL",
  "hr.payroll.run_pay": "Gaji dibayarkan", "hr.payroll.settings": "Pengaturan penggajian diubah",
  approval_matrix_approve: "Persetujuan diberikan", approval_matrix_reject: "Persetujuan ditolak",
  special_order_customer_acc: "Pelanggan ACC pesanan khusus", special_order_customer_revisi: "Pelanggan minta revisi pesanan khusus",
  special_order_price_locked: "Harga pesanan khusus dikunci", special_order_converted_to_so: "Pesanan khusus dijadikan SO",
  special_order_prepare_shipment: "Pesanan khusus disiapkan kirim", special_order_fulfillment_realize: "Pemenuhan pesanan khusus direalisasi",
  special_order_fulfillment_route: "Rute pemenuhan pesanan khusus ditetapkan", special_order_fulfillment_cancel: "Pemenuhan pesanan khusus dibatalkan",
  special_order_redesign: "Pesanan khusus didesain ulang",
  outbound_scan_pick: "Scan ambil barang keluar", outbound_dispatched: "Barang keluar diberangkatkan",
  inbound_scan_label: "Label penerimaan dicetak", grn_manual_entry: "Penerimaan dicatat manual",
  sample_cut: "Sample dipotong", cutting_handoff: "Hasil potong diserahkan", loading_check_override: "Cek muat dikecualikan",
  rfid_simulated_tags: "Tag RFID simulasi dibuat", ai_tool_run_report: "Laporan alat AI dijalankan",
  catalogue_soft_changed: "Katalog diubah", sales_target_set: "Target penjualan ditetapkan",
  pr_realized_po: "PR direalisasi jadi PO", pr_realized_makloon: "PR direalisasi jadi makloon",
  so_rolls_released_partial: "Sebagian roll SO dilepas", so_line_reallocated: "Baris SO dialokasikan ulang",
  sample_forwarded_to_warehouse: "Sample diteruskan ke gudang", design_paper_check: "Cek kertas desain",
  design_paper_uncheck: "Cek kertas desain dibatalkan", design_submit: "Desain diajukan", design_submit_final: "Desain final diajukan",
  design_approve: "Desain di-ACC", design_start_review: "Review desain dimulai", design_hold: "Desain ditahan",
  design_release_hold: "Tahanan desain dilepas", sales_return_journey_scan: "Scan perjalanan retur",
  sales_return_complaint_set: "Keluhan retur dicatat", sales_return_logistics_set: "Logistik retur ditetapkan",
  sales_return_roll_decisions: "Keputusan per roll retur", sales_return_milestone: "Tahap retur dicatat",
  sales_return_shipment: "Pengiriman retur dicatat", sales_return_cutloss_recorded: "Potongan cacat retur dicatat",
  sales_return_cutloss_split: "Roll retur dipecah (potongan cacat)", sales_return_cutloss_return_sj: "SJ potongan baik retur dibuat",
  material_loss_recorded: "Susut bahan dicatat", material_loss_approved: "Susut bahan disetujui",
  role_access_updated: "Akses peran diubah", role_access_reset: "Akses peran diatur ulang", permissions_updated: "Matriks izin diubah",
  so_approval_approved: "Persetujuan SO diberikan", so_approval_rejected: "Persetujuan SO ditolak",
  so_special_price_requested: "Harga khusus SO diajukan", entity_provisioned: "Badan usaha disiapkan",
};

const humanize = (key) => String(key || "").replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const _own = (map, k) => (Object.prototype.hasOwnProperty.call(map, k) ? map[k] : undefined);

// UAT 24 Okt (audit UI tahap 2) — G0-16: kunci audit berpola `<sumber daya>_<kata kerja>` dirakit dari dua peta ini
// ("reservation_expired" → "Reservasi kedaluwarsa", "bank_line_ignored" → "Baris mutasi bank diabaikan") supaya
// kunci baru tidak jatuh ke humanize Inggris. Kunci yang tidak cocok → "Aksi lain" (kode mentah hanya untuk tooltip).
const AUDIT_VERB = {
  created: "dibuat", create: "dibuat", updated: "diubah", update: "diubah", changed: "diubah", edited: "diubah",
  deleted: "dihapus", delete: "dihapus", removed: "dihapus", cancelled: "dibatalkan", cancel: "dibatalkan",
  rejected: "ditolak", reject: "ditolak", approved: "disetujui", approve: "disetujui", deactivated: "dinonaktifkan",
  activated: "diaktifkan", reactivated: "diaktifkan kembali", set: "ditetapkan", submitted: "diajukan", submit: "diajukan",
  added: "ditambahkan", decided: "diputuskan", requested: "diminta", released: "dilepas", completed: "diselesaikan",
  finished: "selesai", resolved: "diselesaikan", voided: "dianulir", started: "dimulai", run: "dijalankan",
  reopened: "dibuka kembali", issued: "diterbitkan", imported: "diimpor", reversed: "dibalik", reset: "diatur ulang",
  generated: "dihasilkan", assigned: "ditugaskan", verified: "diverifikasi", revoked: "dicabut", recorded: "dicatat",
  received: "diterima", posted: "diposting", matched: "dicocokkan", confirmed: "dikonfirmasi", uploaded: "diunggah",
  settled: "diselesaikan", sent: "dikirim", saved: "disimpan", reverted: "dikembalikan", printed: "dicetak", paid: "dibayar",
  closed: "ditutup", unlocked: "dibuka kuncinya", proposed: "diusulkan", expired: "kedaluwarsa", delivered: "diserahkan",
  inspected: "diinspeksi", transferred: "dipindahkan", replaced: "diganti", reminded: "diingatkan", split: "dipecah",
  merged: "digabung", disbursed: "dicairkan", escalated: "dieskalasi", shipped: "dikirim", archived: "diarsipkan",
  renamed: "diganti nama", corrected: "dikoreksi", overridden: "dikecualikan", override: "dikecualikan",
  applied: "diterapkan", converted: "dikonversi", awarded: "pemenang ditetapkan", quoted: "penawaran masuk",
  encoded: "dienkode", retired: "dipensiunkan", ignored: "diabaikan", unignored: "batal diabaikan", booked: "dibukukan",
  allocated: "dialokasikan", waived: "dibebaskan", adjusted: "disesuaikan", disposed: "dihapusbukukan",
  synced: "disinkronkan", repaid: "dilunasi", linked: "ditautkan", unlinked: "dilepas tautannya", scheduled: "dijadwalkan",
  disputed: "disengketakan", amended: "diamandemen", acknowledged: "ditandai sudah dilihat", seeded: "dibuat awal",
  dispatched: "diberangkatkan", reclosed: "ditutup kembali", rated: "dinilai", accrued: "diakru", opened: "dibuka",
  assessed: "dinilai", hold: "ditahan", undone: "dibatalkan", reconciled: "direkonsiliasi", depreciation: "disusutkan",
};
const AUDIT_RESOURCE = {
  ...MODULE_LABEL,
  reservation: "Reservasi", order: "Pesanan", sales_order: "Pesanan penjualan", design_request: "Permintaan desain",
  sales_return: "Retur penjualan", rnd_sample: "Sample R&D", price_approval: "Persetujuan harga", purchase_return: "Retur pembelian",
  contra_bon: "Kontrabon", vendor_bill: "Tagihan supplier", transfer: "Transfer gudang", settlement: "Pelunasan",
  rnd_spec: "Spesifikasi R&D", pr: "PR", po: "PO", finance_case: "Kasus keuangan", cycle_count: "Stock opname",
  cash_advance: "Kasbon", work_order: "Perintah kerja", user: "Pengguna", supplier_contract: "Kontrak supplier",
  repair_order: "Order perbaikan", payment_term: "Termin pembayaran", makloon_order: "Order makloon", lot: "Lot",
  landed_cost: "Landed cost", interco_transaction: "Transaksi antar-BU", inspection: "Inspeksi", hr_overtime: "Lembur",
  hr_leave: "Cuti", grn: "Penerimaan barang (GRN)", entity_price: "Harga per badan usaha", customer_price: "Harga pelanggan",
  warehouse_site: "Lokasi gudang", warehouse: "Gudang", vehicle_log: "Log kendaraan", vehicle: "Kendaraan",
  uom_rule: "Aturan konversi satuan", uom: "Satuan", template: "Template dokumen", tax_invoice: "Faktur pajak",
  supplier_price: "Harga supplier", supplier: "Supplier", sales_return_policy: "Kebijakan retur", rfid_device: "Perangkat RFID",
  recipe: "Resep proses", product_template: "Template produk", product_media: "Foto produk", product: "Produk",
  period_unlock: "Buka kunci periode", payment_plan: "Rencana pembayaran", ocr_sample: "Contoh OCR",
  makloon_claim: "Klaim makloon", makloon: "Makloon", logistics: "Pengiriman", lead: "Prospek", journal_entry: "Jurnal",
  internal_request: "Permintaan internal", interco_tax_invoice: "Faktur pajak antar-BU", interco_return: "Retur antar-BU",
  incentive_rate: "Tarif insentif", hr_shift: "Shift", hr_org_unit: "Unit organisasi", hr_kpi: "KPI karyawan",
  hr_geofence: "Geofence absensi", hr_employee: "Karyawan", hr_device: "Perangkat absensi", grn_line: "Baris GRN",
  grn_count: "Hitung GRN", gl_account: "Akun GL", fleet_vehicle: "Armada", fixed_asset: "Aset tetap",
  entity_master: "Master badan usaha", design_gallery: "Galeri desain", design_colorway: "Colorway desain",
  data_hygiene: "Kebersihan data", customer: "Pelanggan", color: "Warna", category: "Kategori", budget: "Anggaran",
  bom: "BOM", vendor_bill_payment: "Pembayaran tagihan supplier", variants: "Varian", stock_wip: "Stok WIP",
  stock_hold: "Tahanan stok", special_order: "Pesanan khusus", sample: "Sample", roll: "Roll", rfq: "RFQ",
  interco_settlement: "Pelunasan antar-BU", interco_loan: "Pinjaman antar-BU", mkt_post: "Posting pemasaran",
  mkt_campaign: "Kampanye pemasaran", mkt_template: "Template pemasaran", bank_line: "Baris mutasi bank",
  bank_rule: "Aturan bank", bank_account: "Rekening bank", bank_statement: "Mutasi bank", cash_transaction: "Transaksi kas",
  blanket_po: "Kontrak blanket", customer_feedback: "Umpan balik pelanggan", custom_role: "Peran kustom",
  config_value: "Nilai pengaturan", design_category: "Kategori desain", design_claim: "Klaim desain", design: "Desain",
  putaway_order: "Perintah simpan", putaway_exception: "Pengecualian simpan", outbound_tasks: "Tugas barang keluar",
  outbound_task: "Tugas barang keluar", inspection_hold: "Tahanan inspeksi", inspection_line: "Baris inspeksi",
  inspection_random_check: "Cek acak inspeksi", rfid_print_job: "Cetak tag RFID", rfid_verify: "Verifikasi RFID",
  material_loss: "Susut bahan", customer_address: "Alamat pelanggan", sales_target: "Target penjualan",
  role_access: "Akses peran", settings: "Pengaturan", scheduler: "Penjadwal", rnd_round: "Ronde R&D", rnd_product: "Produk R&D",
  rnd_division: "Divisi R&D", rnd_revalidation: "Validasi ulang R&D", rnd_labdip_batch: "Batch labdip",
  rnd_round_attachment: "Lampiran ronde R&D", sales_return_attachment: "Lampiran retur", price_approval_attachment: "Lampiran persetujuan harga",
  purchase_return_attachment: "Lampiran retur pembelian", interco_return_attachment: "Lampiran retur antar-BU",
  design_request_reference: "Referensi permintaan desain", design_request_design: "Desain permintaan",
  makloon_material: "Bahan makloon", loading_check: "Cek muat", roll_cut: "Potong roll", cycle_count_roll: "Roll stock opname",
  interco_warehouse_task: "Tugas gudang antar-BU", interco_return_task: "Tugas retur antar-BU", wms_task: "Tugas gudang",
  fulfillment: "Pemenuhan", gl_mapping: "Pemetaan akun GL", pph_record: "Catatan PPh", penalty: "Denda",
  pdf_template: "Template PDF", payment_variance: "Selisih bayar", input_tax: "PPN masukan", ic_elimination: "Eliminasi antar-BU",
  contra_bon_deduction: "Potongan kontrabon", hr_attendance: "Absensi", hr_visit: "Kunjungan", expense_category: "Kategori biaya",
  ar_receipt: "Penerimaan piutang", period: "Periode", entity: "Badan usaha", user_password: "Sandi pengguna",
  user_sessions: "Sesi pengguna", products: "Produk", warehouses: "Gudang", customers: "Pelanggan", amendment: "Amandemen",
  credit_override: "Override kredit", collection: "Penagihan", wizard_pr: "Wizard PR", wizard_interco: "Wizard antar-BU",
};

/** Label aksi audit tanpa humanize Inggris: peta tetap → pola `<sumber daya>_<kata kerja>` → "Aksi lain". */
export function auditActionInfo(key) {
  const k = String(key || "");
  const fixed = _own(AUDIT_ACTION_LABEL, k);
  if (fixed) return { label: fixed, known: true, code: k };
  const m = /^(.+)_([a-z]+)$/.exec(k.toLowerCase());
  if (m) {
    const verb = _own(AUDIT_VERB, m[2]);
    const res = _own(AUDIT_RESOURCE, m[1]);
    if (verb && res) return { label: `${res} ${verb}`, known: true, code: k };
  }
  return { label: "Aksi lain", known: false, code: k };
}

export const moduleLabel = (key) => MODULE_LABEL[key] || humanize(key);
export const actionLabel = (key) => ACTION_LABEL[key] || humanize(key);
/** UAT 24 Okt — G0-16: tidak lagi jatuh ke humanize Inggris ("Reservation Expired"); kunci tak dikenal → "Aksi lain".
 *  Pakai `auditActionInfo(key).known` untuk menampilkan kode mentah di tooltip. */
export const auditActionLabel = (key) => auditActionInfo(key).label;
export const isKnownAuditAction = (key) => auditActionInfo(key).known;

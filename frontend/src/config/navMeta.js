// ─── NAV META DATA (SSOT untuk TopBar kicker/title, role-home, guidance) ──────
// Dipisah dari navigationConfig.js agar file config di bawah batas guardrail.

// PAGE META (SSOT untuk TopBar kicker + title)
export const PAGE_META = {
  // S#094 — nama menu 1–2 kata; istilah teknis/singkatan (POS, CRM, WMS, PO, AP, BOM, R&D) hidup di judul halaman.
  // 23 Okt — 12 kunci ganda dihapus dari blok ini (ESLint no-dupe-keys): entri di bawah yang SELAMA INI berlaku.
  "customers-master":     { kicker: "Pelanggan",      title: "Impor/Ekspor & Status Pelanggan" },
  "permission-matrix":    { kicker: "Pengaturan · Pengguna & Hak Akses", title: "Peran & Hak Akses" },
  "doc-templates-basic":  { kicker: "Pengaturan · Dokumen & Notifikasi", title: "Template Dokumen Dasar" },
  "home":                 { kicker: "Kerja Saya",     title: "Beranda" },
  admin:                  { kicker: "Pengaturan · Sistem", title: "Integrasi & Audit" },
  "admin-home":           { kicker: "Eksekutif",      title: "Control Tower" },
  "manager-home":         { kicker: "Manajer",        title: "Dasbor Manajer \u00b7 Persetujuan, Target Tim & Keterlambatan" },
  sales:                  { kicker: "Penjualan",      title: "POS / Sales Portal" },
  "sales-home":           { kicker: "Penjualan",      title: "Performa Saya" },
  "customers-crm":        { kicker: "Penjualan",      title: "Pelanggan & CRM \u00b7 Sales Force" },
  "price-approvals":      { kicker: "Persetujuan",      title: "Persetujuan Harga Khusus" },
  orders:                 { kicker: "Penjualan",      title: "Pesanan Penjualan" },
  // FASE E-8 (E8.7/E8.20) — dua MEJA KERJA peran baru. Tanpa baris ini kepala halaman
  // jatuh ke cadangan "BERANDA · Kain Nusantara" di layar yang justru jadi tempat kerja
  // harian dua peran (kelas bug yang ditangkap `check_nav_map.py` CHECK 5).
  "sales-admin-desk":     { kicker: "Admin Sales",    title: "Meja Admin Sales \u00b7 Antrean Alur Pesanan" },
  // MN-T2 — Meja Finance apa adanya → Beranda Keuangan › Perlu Tindakan (satu daftar berkelompok berizin).
  "finance-desk":         { kicker: "Keuangan \u00b7 Beranda Keuangan", title: "Perlu Tindakan \u00b7 Pekerjaan Uang yang Menunggu" },
  "md-desk":              { kicker: "MD",             title: "Meja MD \u00b7 Desain, Sample & Bahan" },
  "my-desk":              { kicker: "Kerja saya",     title: "Meja Saya \u00b7 Giliran & Antrean Peran" },
  "tanya-kn":             { kicker: "Asisten analitik", title: "Tanya KN \u00b7 Laporan & Pertanyaan Data" },
  "warehouse-admin-desk": { kicker: "Admin Gudang",   title: "Meja Admin Gudang \u00b7 Operasi Gudang & Logistik" },
  "sample-admin-desk":    { kicker: "Admin Sample",   title: "Meja Admin Sample \u00b7 Antrean Pesanan Sample" },
  "sample-orders":        { kicker: "Penjualan",      title: "Pesanan Sample (SOS) \u00b7 Terpisah dari SO Biasa" },
  amendments:             { kicker: "Keuangan \u00b7 Kendali", title: "Pusat Amandemen \u00b7 Koreksi Ber-alasan & Ber-jejak" },
  "tax-invoices":         { kicker: "Keuangan \u00b7 Pajak", title: "Faktur Pajak Keluaran" },
  "returns":              { kicker: "Retur",          title: "Retur Pelanggan & Barang Sisa" },
  "returns-hub":          { kicker: "Retur",          title: "Retur \u00b7 Pelanggan \u00b7 Antar-PT \u00b7 Supplier" },
  "interco-returns":      { kicker: "Retur",          title: "Retur Antar-PT \u00b7 Keluar & Masuk" },
  "return-policies":      { kicker: "Pengaturan · Penjualan", title: "Kebijakan Retur Jual" },
  "special-orders":       { kicker: "Penjualan",      title: "Pesanan Khusus (OD)" },
  // FASE E-7 (E7d) — permintaan barang antar badan usaha. Tanpa baris ini judul layar
  // jatuh ke cadangan "Kain Nusantara" / kicker "Workspace" (pengguna kehilangan konteks).
  "internal-requests":    { kicker: "Antar-PT", title: "Permintaan Internal (PIN)" },
  "keep-pending":         { kicker: "Penjualan",      title: "Keep & Pending · pesanan menunggu" },
  "repair-orders":        { kicker: "Gudang",         title: "Perbaikan · repair, celup ulang, finishing ulang" },
  // FASE D — papan pekerjaan desain (CHECK 5 `check_nav_map`: setiap layar wajib berjudul).
  "design-requests":      { kicker: "Desain",         title: "Permintaan Desain (DSR)" },
  "marketing-hub":        { kicker: "Marketing",      title: "Marketing & Sosial Media" },
  "mkt-calendar":         { kicker: "Marketing",      title: "Kalender Konten \u00b7 Rencana, Review & Jadwal Tayang" },
  "mkt-campaigns":        { kicker: "Marketing",      title: "Kampanye \u00b7 Tema & Periode Konten" },
  "mkt-analytics":        { kicker: "Marketing",      title: "Dashboard Sosmed \u00b7 KPI, Tren & Performa Konten" },
  "mkt-accounts":         { kicker: "Marketing", title: "Akun Sosmed \u00b7 per PT" },
  // FASE I — dokumen inspeksi & QC (SPK). Tanpa baris ini judul layar jatuh ke
  // cadangan "Kain Nusantara" dan CHECK 5 `check_nav_map` memerah.
  "inspections":          { kicker: "Kualitas",       title: "SPK Inspeksi & QC (INS)" },
  "pricelist":            { kicker: "Produk & Harga", title: "Harga per PT" },
  "color-library":        { kicker: "Produk & Harga", title: "Pustaka Warna" },
  "domain-registry":      { kicker: "Pengaturan · Sistem", title: "Kamus Aturan Kain" },
  "product-templates":    { kicker: "Produk & Harga", title: "Produk & Varian" },
  "approval-inbox":       { kicker: "Persetujuan",      title: "Pusat Persetujuan" },
  "my-approvals":         { kicker: "Persetujuan",      title: "Persetujuan Saya \u00b7 Matriks Divisi (ACC Desain \u00b7 Sample \u00b7 PO Custom \u00b7 PR \u00b7 Klaim Makloon)" },
  "approval-rules":       { kicker: "Pengaturan · Persetujuan", title: "Aturan Persetujuan" },
  "entity-masters":       { kicker: "Pengaturan · Perusahaan (PT)", title: "Master per PT" },
  "client-dataset-import": { kicker: "Pengaturan · Sistem", title: "Impor Data Awal" },
  "grade-master":         { kicker: "Pengaturan · Gudang, Pembelian & Produksi", title: "Grade Mutu" },
  // Fase 3 · P2 (D-01) — Template PDF + Template Dokumen Dasar = satu layar "Template Dokumen".
  "pdf-templates":        { kicker: "Pengaturan · Dokumen & Notifikasi", title: "Template Dokumen \u00b7 Kop, Tata Letak & Desainer PDF" },
  "document-center":      { kicker: "Dokumen",        title: "Pusat Dokumen" },
  "doc-trace":            { kicker: "Dokumen",        title: "Jejak Dokumen (Relasi Antar Surat)" },
  "payment-plans":        { kicker: "Keuangan",       title: "Rencana Pembayaran & Denda" },
  purchasing:             { kicker: "Pembelian",      title: "Pesanan Pembelian (PO)" },
  "po-board":             { kicker: "Pembelian",      title: "Papan PO per Lini" },
  "blanket-po":           { kicker: "Pembelian",      title: "Kontrak Blanket PO · Panggilan Kirim" },
  "purchase-requisitions":{ kicker: "Pembelian",      title: "Permintaan Pembelian (PR)" },
  reorder:                { kicker: "Pembelian",      title: "Saran Reorder · Isi Ulang Stok" },
  suppliers:              { kicker: "Pembelian",      title: "Master Pemasok (Supplier)" },
  makloons:               { kicker: "Pembelian",      title: "Mitra Makloon (Subkontraktor)" },
  // Fase 3 · P8 (D-25) — nama diperjelas: resep makloon ≠ BOM produksi in-house (Gudang › BOM Produksi In-House).
  "process-recipes":      { kicker: "Pembelian",      title: "Resep Proses Makloon · Konversi Bahan → Hasil" },
  // Fase 3 · P8 (D-22) — satu layar: rekap susut & klaim + skor mitra (dulu tersebar di Klaim & rincian mitra).
  "makloon-claim-recap":  { kicker: "Pembelian",      title: "Kinerja Mitra Makloon · Rekap Susut, Klaim & Skor Mitra" },
  // Fase 3 · P8 (D-23) — tab tersembunyi di Master Pembelian (peran Kontrak); layar sama dengan Produk & Harga.
  "supplier-internal-prices": { kicker: "Pembelian",  title: "Harga Internal Antar-PT" },
  "makloon-orders":       { kicker: "Pembelian",      title: "Order Makloon (Subkontrak \u00b7 Bahan di Mitra)" },
  "makloon-claims":       { kicker: "Pembelian",      title: "Klaim Selisih Makloon \u00b7 Persetujuan & Skor Mitra" },
  "supplier-contracts":   { kicker: "Pembelian",      title: "Kontrak Mitra & Supplier \u00b7 Tarif, Susut & Toleransi" },
  "supplier-items":       { kicker: "Pembelian",      title: "Barang Supplier \u00b7 Peta SKU/Nama Supplier & Impor Massal" },
  "md-products":          { kicker: "Produk & Harga", title: "Produk & Varian" },
  // FASE F — R&D (hulu rantai: spesifikasi → labdip/proofing → kontrak).
  "rnd-specs":            { kicker: "R&D",             title: "Spesifikasi Produk (R&D) \u00b7 Target Kain, Warna & Desain" },
  "rnd-samples":          { kicker: "R&D",             title: "R&D Produk Baru \u00b7 Handfeel \u2192 Labdip \u2192 Produk" },
  "rnd-revalidation":     { kicker: "R&D",             title: "Uji Ulang SKU \u00b7 supplier berkontrak" },
  "rnd-labdip":           { kicker: "R&D",             title: "Labdip (Master) \u00b7 Sample Warna per Supplier" },
  "rnd-handfeel":         { kicker: "R&D",             title: "Handfeel (Master) \u00b7 Sample Pegangan & Konstruksi Kain" },
  "rnd-proofing":         { kicker: "R&D",             title: "Proofing (Master) \u00b7 Sample Cetak Desain" },
  "rnd-reports":          { kicker: "R&D",             title: "Laporan R&D \u00b7 SLA Ronde & Tahap Produk" },
  // PS-18 — menu DESAINER (terpisah dari R&D): orang + karyanya.
  "designer-kpi":         { kicker: "Desainer",        title: "KPI Desainer \u00b7 Tepat Waktu, Pengulangan & Eskalasi SLA" },
  "rnd-designs":          { kicker: "Desainer",        title: "Desain & Pattern (Master) \u00b7 Kode, Versi & Pengesahan" },
  "rnd-divisions":        { kicker: "Pengaturan · Persetujuan", title: "Persetujuan R&D" },
  "md-categories":        { kicker: "Produk & Harga", title: "Kategori Produk" },
  "md-uoms":              { kicker: "Produk & Harga", title: "Satuan & Konversi" },
  "uom-conversions":      { kicker: "Produk & Harga", title: "Satuan & Konversi" },
  "inventory-lots":       { kicker: "Gudang",         title: "Lot & Silsilah \u00b7 Traceability, Recall & Label" },
  "md-warehouses":        { kicker: "Gudang",         title: "Gudang (Master) \u00b7 Lokasi & Bin" },
  "purchase-approval":    { kicker: "Persetujuan",      title: "Persetujuan Pembelian" },
  "cash-management":      { kicker: "Keuangan",       title: "Transaksi Kas" },
  "purchase-returns":     { kicker: "Retur",          title: "Retur ke Supplier (Nota Debit)" },
  "vendor-bills":         { kicker: "Pembelian",      title: "Tagihan Supplier · 3-Way Matching" },
  "landed-cost":          { kicker: "Pembelian",      title: "Biaya Masuk (landed cost) · Alokasi HPP Roll" },
  "input-tax":            { kicker: "Keuangan \u00b7 Pajak", title: "Faktur Pajak Masukan · PPN Masukan & Rekap" },
  "rfq":                  { kicker: "Pembelian",      title: "RFQ / Penawaran · Tender & Banding Harga Supplier" },
  operations:             { kicker: "Operasi Gudang", title: "Stok, Transfer, Opname & Kesehatan" },
  "qc-inspection":        { kicker: "Kualitas",       title: "Antrean QC Kedatangan" },
  "quality-hub":          { kicker: "Kualitas",       title: "Kualitas · QC & Inspeksi" },
  "inventory-board":      { kicker: "Gudang",         title: "Status Stok & ATP" },
  "stock-buckets":        { kicker: "Gudang",         title: "Stok Multi-Kantong (WIP / Ditahan / Dalam Perjalanan)" },
  "interco-transfers":    { kicker: "Gudang", title: "Transfer Antar-PT" },
  escalations:            { kicker: "Gudang",         title: "Eskalasi Gudang" },
  documents:              { kicker: "Dokumen",        title: "Pusat Cetak & Label" },
  reports:                { kicker: "Analitik",       title: "Dasbor & Analitik" },
  costing:                { kicker: "Analitik (BI)",  title: "Margin & HPP (WAC)" },
  // Coming Soon views (cs-* yang benar-benar belum live)
  "cs-price-list":        { kicker: "Produk & Harga", title: "Harga per Pelanggan" },
  "internal-prices":      { kicker: "Produk & Harga", title: "Harga Internal Antar-PT" },
  "amendment-reasons":    { kicker: "Pengaturan · Penjualan", title: "Alasan Koreksi" },
  // Fase 3 · P2 (D-03) — tarif per kategori + bawaan komisi (`commission.*`) digabung di satu layar.
  // KM-T5 — id lama = alias (viewAliases.js); judul rute cadangannya = layar tujuan.
  "incentive-rates":      { kicker: "SDM · Kinerja & Insentif", title: "Target & Aturan Insentif" },
  "incentive-setup":      { kicker: "SDM · Kinerja & Insentif", title: "Target & Aturan Insentif" },   // KM-T1
  "incentive-capaian":    { kicker: "SDM · Kinerja & Insentif", title: "Capaian Insentif" },   // KM-T2
  "incentive-sheets":     { kicker: "SDM · Kinerja & Insentif", title: "Lembar Insentif" },   // KM-T3
  "bank-recon-rules":     { kicker: "Pengaturan · Keuangan & Pajak", title: "Bank" },
  "cs-bom":               { kicker: "Pembelian",      title: "BOM Printing" },
  "cs-stock-analytics":   { kicker: "Gudang",         title: "Analitik Stok (Cepat/Lambat/Mati)" },
  "export-center":        { kicker: "Laporan",        title: "Pusat Export" },
  "goods-receipts":       { kicker: "Operasi Gudang", title: "Barang Masuk · Surat Jalan, OCR & Hitung Fisik" },
  "wms-outbound":         { kicker: "Operasi Gudang", title: "Barang Keluar · Ambil & Kirim Pesanan" },
  "wms-cutting":          { kicker: "Operasi Gudang", title: "Cutting · Potong Sample & Potong Roll" },
  "settings-receiving-ocr": { kicker: "Pengaturan · Gudang, Pembelian & Produksi", title: "Penerimaan Barang" },
  "wms-locations":        { kicker: "Gudang",         title: "Lokasi Gudang & Penempatan Rak" },
  "production":           { kicker: "Gudang",         title: "BOM Produksi In-House \u00b7 BOM & Work Order" },
  "scheduler":            { kicker: "Pengaturan · Dokumen & Notifikasi", title: "Pengingat Otomatis" },
  "cs-rfid-lokasi":       { kicker: "RFID",           title: "Lokasi RFID" },
  "cs-rfid-tags":         { kicker: "RFID",           title: "Tag RFID" },
  "cs-rfid-devices":      { kicker: "Pengaturan · Sistem", title: "Perangkat RFID (Pembaca / Gerbang)" },
  "cs-rfid-gate":         { kicker: "RFID",           title: "Monitor Gerbang" },
  "chart-of-accounts":    { kicker: "Keuangan",       title: "Bagan Akun" },   // MN-T1 — label Inggris dicabut
  "general-ledger":       { kicker: "Keuangan",       title: "Buku Besar · Jurnal Umum" },
  "financial-statements": { kicker: "Keuangan",       title: "Laporan Keuangan · Laba-Rugi, Neraca & Arus Kas" },
  "finance-tower":        { kicker: "Keuangan",       title: "Dasbor Keuangan" },
  // Fase 3 · P8 (D-11) — satu layar margin: realisasi + margin katalog (dulu juga Analitik › Margin & HPP).
  "profitability":        { kicker: "Keuangan",       title: "Profitabilitas & Margin · Realisasi & Margin Katalog (HPP/WAC)" },
  "cashflow-forecast":    { kicker: "Keuangan",       title: "Proyeksi Arus Kas · Likuiditas" },
  "budget":               { kicker: "Keuangan",       title: "Anggaran vs Realisasi · Commitment Control" },
  "bank-accounts":        { kicker: "Keuangan",       title: "Kas & Bank · Rekening & Saldo" },
  // FASE G-8 — tanpa entri ini TopBar jatuh ke fallback "Workspace · Kain Nusantara"
  // sehingga pengguna kehilangan jejak posisinya (temuan penutupan fase).
  "bank-reconciliation":  { kicker: "Keuangan",       title: "Kas & Bank · Rekonsiliasi Bank Otomatis" },
  "finance-cases":        { kicker: "Keuangan",       title: "Pusat Kasus Keuangan" },
  // FASE G-7 — tanpa entri ini TopBar jatuh ke fallback "Workspace · Kain Nusantara"
  // sehingga pengguna kehilangan jejak posisinya (pelajaran penutupan G-8).
  "contra-bons":          { kicker: "Pembelian",      title: "Kontrabon \u00b7 Siklus Tukar Faktur Supplier" },
  "gr-ir":                { kicker: "Keuangan",       title: "GR/IR \u00b7 Barang Diterima Belum Ditagih" },   // PK-28
  // FASE G-6 — antar-PT sebagai jual-beli (bukan pindah gudang).
  "interco-transactions": { kicker: "Pembelian", title: "Transaksi Antar-PT \u00b7 Jual-Beli dalam Grup" },
  // KP-T9 — enam layar baru (bagian layar wadah lama yang dinaikkan menjadi tab hub Pengaturan).
  "settings-pt-profile":   { kicker: "Pengaturan · Perusahaan (PT)", title: "Profil PT" },
  "settings-pt-readiness": { kicker: "Pengaturan · Perusahaan (PT)", title: "Kesiapan PT" },
  "settings-accounts":     { kicker: "Pengaturan · Pengguna & Hak Akses", title: "Akun" },
  "settings-role-check":   { kicker: "Pengaturan · Pengguna & Hak Akses", title: "Cek Peran" },
  "settings-attendance-devices": { kicker: "Pengaturan · SDM", title: "Mesin Absen" },
  "settings-whatsapp":     { kicker: "Pengaturan · Dokumen & Notifikasi", title: "WhatsApp" },
  "settings-config":      { kicker: "Pengaturan · Sistem", title: "Cari Semua Pengaturan" },
  // Fase 3 · P2 (P16-K1) — Pusat Pengaturan terkunci ke kelompok registri tiap domain (configGroupViews.js).
  "settings-cfg-approval":   { kicker: "Pengaturan · Persetujuan", title: "Ketegasan, Pengingat & Dokumen \u00b7 Persetujuan, pengingat & dokumen" },
  "settings-dual-control":   { kicker: "Pengaturan · Persetujuan", title: "Kontrol Dua Orang \u00b7 Pengaju dan Pemutus" },
  "settings-doc-numbering":  { kicker: "Pengaturan · Dokumen & Notifikasi", title: "Penomoran Dokumen \u00b7 Awalan, Lebar, dan Deret per PT" },
  "settings-cfg-sales":      { kicker: "Pengaturan · Penjualan", title: "Aturan Penjualan \u00b7 Penjualan & harga, Retur & koreksi dokumen" },
  "settings-cfg-warehouse":  { kicker: "Pengaturan · Gudang, Pembelian & Produksi", title: "Aturan Gudang & Mutu \u00b7 Penerimaan barang & lot, Mutu kain (QC), Stok, alokasi & potong" },
  "settings-cfg-purchasing": { kicker: "Pengaturan · Gudang, Pembelian & Produksi", title: "Aturan Pembelian & Makloon \u00b7 Pembelian, makloon & tagihan pemasok" },
  "settings-cfg-finance":    { kicker: "Pengaturan · Keuangan & Pajak", title: "Aturan Keuangan & Pajak \u00b7 Pembayaran pelanggan, Pajak, pembukuan & antar-PT, Bank & uang yang nyangkut" },
  "settings-cfg-hr":         { kicker: "Pengaturan · SDM", title: "Aturan SDM & Penggajian \u00b7 Gaji & SDM" },
  "settings-cfg-rnd":        { kicker: "Pengaturan · Gudang, Pembelian & Produksi", title: "R&D & Desain \u00b7 R&D & desain" },
  "settings-cfg-documents":  { kicker: "Pengaturan · Persetujuan", title: "Aturan Dokumen \u00b7 Referensi, Jejak & Tanda Tangan" },
  "settings-cfg-notify":     { kicker: "Pengaturan · Persetujuan", title: "Penerima Notifikasi \u00b7 Siapa Menerima Peringatan Apa" },
  "settings-cfg-system":     { kicker: "Pengaturan · Sistem", title: "AI & Tampilan \u00b7 Sistem, AI & tampilan" },
  // D-29 — layar Perangkat (mesin absen + RFID); KP-T9 — bagian RFID kini tab sendiri, mesin absen di SDM.
  "settings-devices":        { kicker: "Pengaturan · Sistem", title: "Perangkat RFID" },
  // P16-K1 — Koreksi Harga pindah dari Pusat Pengaturan ke Produk & Harga.
  "price-corrections":       { kicker: "Produk & Harga", title: "Koreksi Harga & Daftar Dampak" },
  "entities-access":      { kicker: "Pengaturan · Perusahaan (PT)", title: "Profil PT (alamat lama)" },
  "cash-advances":        { kicker: "Kas & Petty Cash", title: "Pengajuan Dana (PD) · Cash Advance" },
  "settlements":          { kicker: "Kas & Petty Cash", title: "Pertanggungjawaban (LPJ) · Petty Cash" },
  "expense-categories":   { kicker: "Pengaturan · Keuangan & Pajak", title: "Kategori Beban → Akun COA" },
  "gl-account-mappings":  { kicker: "Pengaturan · Keuangan & Pajak", title: "Pemetaan Akun" },
  "reimburse-payables":   { kicker: "Kas & Petty Cash", title: "Hutang Reimburse Karyawan · Umur Hutang" },
  "vehicle-logs":         { kicker: "Aset & GA",      title: "Penggunaan & Biaya Kendaraan" },
  "fixed-assets":         { kicker: "Kas & Aset",     title: "Aset Tetap \u00b7 Penyusutan & Disposal" },
  "cs-pajak":             { kicker: "Keuangan \u00b7 Pajak", title: "Pajak (PPN & PPh)" },
  "ar-aging":             { kicker: "Keuangan",       title: "AR / Piutang & Umur" },
  "advance-report":       { kicker: "Keuangan",       title: "Uang Muka Pelanggan" },
  "store-credit":         { kicker: "Keuangan",       title: "Store Credit / Saldo Pelanggan" },
  "consolidation":        { kicker: "Keuangan",       title: "Konsolidasi Grup · Eliminasi Intercompany" },
  "closing":              { kicker: "Keuangan",       title: "Tutup Buku · Closing Bulanan & Tahunan" },
  "posting-failures":     { kicker: "Keuangan · Kendali", title: "Posting Gagal · Dokumen dengan Jurnal Gagal" },
  "period-unlock":        { kicker: "Keuangan · Kendali", title: "Buka Periode (Unlock) · Kontrol Ganda & Jendela Waktu" },
  "hr-employees":         { kicker: "SDM (HRD)",      title: "Karyawan" },
  "hr-org-units":         { kicker: "SDM (HRD)",      title: "Struktur Organisasi" },
  "hr-my-profile":        { kicker: "SDM (HRD)",      title: "Profil Saya (ESS)" },
  "logistics":            { kicker: "Logistik",       title: "Pengiriman & Pelacakan \u00b7 Ekspedisi, Armada Sendiri, Foto Muat & POD" },
  "hr-attendance":        { kicker: "SDM (HRD)",      title: "Presensi & Kehadiran" },
  "hr-attendance-setup":  { kicker: "Pengaturan · SDM", title: "Shift & Lokasi Absen" },
  "hr-holidays":          { kicker: "Pengaturan · SDM", title: "Kalender Libur" },   // PY-T3
  "hr-live-tracking":     { kicker: "SDM (HRD)",      title: "Lacak Lapangan · Live Tracking Sales" },
  "hr-visits":            { kicker: "Penjualan",      title: "Kunjungan Sales (Visit)" },
  "hr-payroll-runs":      { kicker: "SDM (HRD)",      title: "Penggajian \u00b7 Proses Gaji" },   // MN-T1
  "hr-payslips":          { kicker: "SDM (HRD)",      title: "Penggajian \u00b7 Proses Gaji" },   // PY-T1 — alias ke Proses Gaji (Cari slip)
  "hr-payroll-remittances": { kicker: "SDM (HRD)",    title: "Penggajian \u00b7 Setoran & Pajak" },   // PK-22 · PY-T4
  "hr-pay-components":    { kicker: "SDM (HRD)",      title: "Penggajian \u00b7 Komponen & Masukan" },   // PY-T1
  "hr-leave":             { kicker: "SDM (HRD)",      title: "Cuti & Izin" },
  "hr-overtime":          { kicker: "SDM (HRD)",      title: "Lembur (Overtime)" },
  "cs-kpi":               { kicker: "SDM (HRD)",      title: "KPI Karyawan (input manual per periode)" },
  "cs-design-gallery":    { kicker: "Desainer",       title: "Galeri Desain (Showcase)" },
  "cs-bi-sales":          { kicker: "Analitik (BI)",  title: "Dasbor Penjualan (Business Intelligence)" },
  "cs-bi-stock":          { kicker: "Analitik (BI)",  title: "Dasbor Stok (Business Intelligence)" },
  "bi-finance":           { kicker: "Analitik (BI)",  title: "BI Keuangan · Tren, Rasio & Perbandingan PT" },
  "cs-bi-hrd":            { kicker: "Analitik (BI)",  title: "Dasbor BI SDM" },
  // MN-T1 — view baru (tab hub yang merender layar lama tanpa perubahan) + Kas Kecil (dulu id hub, kini pembungkus).
  "collection-worklist":  { kicker: "Keuangan \u00b7 Piutang", title: "Penagihan & Penerimaan \u00b7 Daftar Kerja Penagihan" },
  "customer-credit":      { kicker: "Keuangan \u00b7 Piutang", title: "Titipan & Saldo Kredit Pelanggan" },
  "credit-overrides":     { kicker: "Keuangan \u00b7 Piutang", title: "Kredit & Plafon \u00b7 Daftar Kerja Kredit" },   // CR-T5
  "sales-performance":    { kicker: "SDM \u00b7 Kinerja & Insentif", title: "Capaian Insentif" },   // KM-T5 — alias
  "incentive-schemes":    { kicker: "SDM \u00b7 Kinerja & Insentif", title: "Target & Aturan Insentif" },   // KM-T5 — alias
  "petty-cash":           { kicker: "Keuangan \u00b7 Kas & Bank", title: "Kas Kecil \u00b7 Pengajuan Dana, Pertanggungjawaban & Hutang Reimburse" },
  "cash-holdings":        { kicker: "Keuangan \u00b7 Kas & Bank", title: "Titipan Sales \u00b7 Tunai yang Dipegang Sales & Setorannya" },
};

// ROLE-HOME REGISTRY (F5) — landing per role
// PR-T4 — nilai di bawah adalah CADANGAN sebelum jawaban `GET /api/roles` datang: halaman awal tiap peran (bawaan
// maupun kustom) diatur di Peran & Hak Akses › Sifat peran dan diisi `roles.registerDynamicRoles`.
export const ROLE_HOME_REGISTRY = {
  admin:     { view: "admin-home", navId: "home" },
  // EPIC 1 · PS-18 — manajer akhirnya punya landing sendiri (dulu mendarat di
  // layar "Laporan" generik sehingga harus berkeliling menu untuk tahu apa yang
  // perlu ditindak).
  manager:   { view: "manager-home", navId: "home" },
  warehouse: { view: "operations", navId: "wms-operations" },
  sales:     { view: "sales-home", navId: "home" },
  // FASE E-8 (E8.1) — dua peran baru. WAJIB sama dengan `backend/role_registry.py`
  // (POC E-8 memeriksa kesamaannya). GELOMBANG 2: keduanya kini mendarat di MEJA
  // KERJA-nya sendiri — antrean pekerjaan hari itu, bukan daftar dokumen generik.
  // Peran pelaksana yang mendarat di daftar harus menyaring sendiri untuk menemukan
  // apa yang perlu ditindak; meja kerja sudah menyusunnya.
  sales_admin: { view: "sales-admin-desk", navId: "sales-admin-desk" },
  // MN-T1 — Meja Finance kini tab "Perlu Tindakan" di Keuangan › Beranda Keuangan (menu yang disorot = hub itu).
  finance:     { view: "finance-desk", navId: "finance-tower" },
  // FASE D — peran ke-7. WAJIB sama dengan `backend/role_registry.py` (diperiksa POC).
  // Desainer mendarat langsung di papan pekerjaannya, bukan di beranda generik.
  designer:    { view: "design-requests", navId: "designer-hub" },
  // FB-02 — sopir mendarat langsung di papan pengiriman.
  driver:      { view: "logistics", navId: "logistics" },
  // Sesi #087 — MD & Admin Gudang mendarat di mejanya.
  md:              { view: "md-desk", navId: "md-desk" },
  warehouse_admin: { view: "warehouse-admin-desk", navId: "warehouse-admin-desk" },
  // REVISI SAMPEL — Admin Sample mendarat di mejanya.
  sample_admin:    { view: "sample-admin-desk", navId: "sample-admin-desk" },
  // P05 IMP-16 — peran mutu mendarat di SPK Inspeksi.
  md_quality:      { view: "inspections", navId: "quality-hub" },
  qc:              { view: "inspections", navId: "quality-hub" },
};

// Smart guidance CTA.
export const GUIDANCE_MAP = {
  admin:                { label: "Audit",       target: "admin" },
  sales:                { label: "Cari Produk", target: "sales" },
  orders:               { label: "Tinjau",      target: "orders" },
  purchasing:           { label: "Buat PO",     target: "purchasing" },
  operations:           { label: "WMS",         target: "operations" },
  "inventory-board":    { label: "Cek ATP",     target: "inventory-board" },
  "interco-transfers":  { label: "Setujui",     target: "interco-transfers" },
  escalations:          { label: "Selesaikan",  target: "escalations" },
  documents:            { label: "Cetak",       target: "documents" },
};

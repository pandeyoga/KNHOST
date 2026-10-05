/**
 * hubTabs.js — TAB per HUB (Restrukturisasi IA — Opsi A).
 *
 * Satu menu = satu proses bisnis; variasi/langkahnya menjadi TAB (bar sekunder di
 * atas view). `view` = activeView yang dirender AppViewRouter (komponen TIDAK
 * berubah, deep-link lama tetap hidup). `roles` = siapa yang boleh melihat tab itu.
 *
 * DIPISAH dari `navStructure.js` (S#FASE-F) karena keduanya sama-sama registri DATA
 * yang terus bertambah setiap ada menu baru; digabung membuat satu berkas terus
 * melewati panduan panjang berkas tanpa alasan struktural.
 * SSOT tetap satu: `navigationConfig.js` me-re-export dari sini.
 */
export const HUB_TABS = {
  "approval-inbox": [
    { view: "approval-inbox",    label: "Inbox Persetujuan",     roles: ["manager", "admin"] },
    { view: "my-approvals",      label: "Persetujuan Saya",      roles: ["manager", "admin"] },
    { view: "price-approvals",   label: "Pengajuan Harga Khusus",   roles: ["admin", "sales", "manager"] },
    { view: "purchase-approval", label: "Riwayat Persetujuan PO",   roles: ["admin", "manager"] },
  ],
  "sales-orders": [
    { view: "orders",            label: "Pesanan (SO)",          roles: ["admin", "sales", "manager"] },
    { view: "amendments",        label: "Koreksi & Amandemen",   roles: ["admin", "sales", "manager"] },
    { view: "returns",           label: "Retur & Barang Sisa",   roles: ["admin", "sales", "manager"] },
    { view: "return-policies",   label: "Kebijakan Retur",       roles: ["admin", "manager"] },
    // FASE E-7 (E7d) — jalur yang dulu buntu: papan stok bilang "tersedia di badan
    // usaha lain", tetapi seluruh menu Antar Entitas 403 untuk sales. Di sini sales
    // MENGAJUKAN, admin/manajer MENINDAK (jadi transaksi antar-PT G-6).
    { view: "internal-requests", label: "Permintaan Internal (PIN)", roles: ["admin", "sales", "manager"] },
  ],
  "customers-crm": [
    { view: "customers-crm",     label: "CRM & Pelanggan",       roles: ["admin", "sales", "manager"] },
    { view: "hr-visits",         label: "Kunjungan Sales",       roles: ["admin", "sales", "manager"] },
    // IA 2026-10 (B1) — impor/ekspor massal & nonaktifkan pelanggan (dulu tab di Master Data & Audit).
    { view: "customers-master",  label: "Impor/Ekspor & Status", roles: ["admin"] },
  ],
  "products-pricing": [
    { view: "md-products",       label: "Produk & Varian",       roles: ["admin", "manager", "sales"] },
    // product-templates remains a routed alias; one visible master-data entry point.
    { view: "md-categories",     label: "Kategori",              roles: ["admin", "manager"] },
    { view: "color-library",     label: "Pustaka Warna",         roles: ["admin", "manager"] },
    { view: "md-uoms",           label: "Satuan & Konversi",     roles: ["admin", "manager"] },
    // Harga: dua lapis dalam SATU tempat — harga per badan usaha lalu harga khusus pelanggan.
    { view: "pricelist",         label: "Harga per Badan Usaha", roles: ["admin", "manager"] },
    { view: "cs-price-list",     label: "Harga per Pelanggan",   roles: ["admin", "manager", "sales"] },
    { view: "internal-prices",   label: "Harga Internal Antar-PT", roles: ["admin"] },
  ],
  "sourcing": [
    { view: "reorder",               label: "Saran Reorder",     roles: ["admin", "manager"] },
    { view: "purchase-requisitions", label: "Permintaan Pembelian", roles: ["admin", "manager", "warehouse"] },
    { view: "rfq",                   label: "RFQ / Penawaran",   roles: ["admin", "manager", "warehouse"] },
  ],
  "purchase-orders": [
    { view: "purchasing",        label: "Pesanan Pembelian (PO)", roles: ["admin", "manager", "finance"] },
    // FASE P — papan PO per lini (kertas kerja MD): progres tahap · Nama Sales
    // dirunut dari pesanan · tanggal masuk & qty terima dihitung sendiri.
    { view: "po-board",          label: "Papan PO per Lini",     roles: ["admin", "manager"] },
    { view: "blanket-po",        label: "Blanket / Kontrak",     roles: ["admin", "manager"] },
    { view: "makloon-orders",    label: "Order Makloon",         roles: ["admin", "manager", "warehouse", "sales"] },
    { view: "makloon-claims",    label: "Klaim Selisih Makloon", roles: ["admin", "manager", "warehouse"] },
  ],
  "master-pembelian": [
    { view: "suppliers",         label: "Pemasok (Supplier)",    roles: ["admin", "manager"] },
    { view: "makloons",          label: "Mitra Makloon",         roles: ["admin", "manager"] },
    { view: "supplier-contracts", label: "Kontrak Mitra & Supplier", roles: ["admin", "manager", "warehouse"] },
    { view: "supplier-items",    label: "Barang Supplier",       roles: ["admin", "manager", "warehouse"] },
    { view: "process-recipes",   label: "Resep Proses",          roles: ["admin", "manager"] },
  ],
  "accounts-payable": [
    { view: "vendor-bills",      label: "Tagihan Supplier",      roles: ["admin", "manager"] },
    // FASE G-7 — kontrabon: satu siklus tukar faktur = satu tanda terima + satu
    // pembayaran. Gudang ikut MELIHAT karena tab "GR Belum Ditagih" adalah pekerjaan
    // mereka (barang sudah diterima tapi faktur supplier belum datang).
    { view: "contra-bons",       label: "Kontrabon (Tukar Faktur)", roles: ["admin", "manager", "warehouse"] },
    // IA 2026-10 (D2) — "Antar Entitas" PINDAH ke grup Akuntansi & Pajak (view sama, fitur utuh).
    { view: "landed-cost",       label: "Landed Cost (HPP)",     roles: ["admin", "manager"] },
    { view: "purchase-returns",  label: "Retur Pembelian (Nota Debit)", roles: ["admin", "manager", "warehouse"] },
  ],
  // FASE F — R&D: hulu rantai (spesifikasi → labdip/proofing → kontrak).
  // warehouse ikut melihat karena dialah yang mengeluarkan bahan sample (PS-19).
  // CATATAN IA (PS-18): "Desain & Pattern" DIPINDAH ke hub `designer-hub` supaya
  // urusan desainer tidak lagi bercampur dengan proses R&D.
  "rnd-hub": [
    // "Spesifikasi Produk" DIKONSOLIDASIKAN ke form Permintaan Sample (bagian 3) & panel
    // "Master data" di rincian sample — tab terpisah dihapus (permintaan pemilik 2026-09).
    { view: "rnd-samples", label: "Permintaan Sample",  roles: ["admin", "manager", "sales", "warehouse", "md", "sales_admin"] },
    // Galeri per JENIS — cermin "Desain & Pattern (Master)" di hub Desainer (permintaan user).
    { view: "rnd-labdip",   label: "Labdip",   roles: ["admin", "manager", "sales", "warehouse", "md", "sales_admin"] },
    { view: "rnd-handfeel", label: "Handfeel", roles: ["admin", "manager", "sales", "warehouse", "md", "sales_admin"] },
    { view: "rnd-proofing", label: "Proofing", roles: ["admin", "manager", "sales", "warehouse", "md", "sales_admin"] },
    { view: "rnd-reports", label: "Laporan R&D",        roles: ["admin", "manager"] },
  ],
  // MARKETING — sosial media & kalender konten.
  "marketing-hub": [
    { view: "mkt-calendar",  label: "Kalender Konten", roles: ["admin", "manager", "designer", "sales", "sales_admin"] },
    { view: "mkt-analytics", label: "Dasbor & Performa", roles: ["admin", "manager", "designer", "sales", "sales_admin"] },
    { view: "mkt-campaigns", label: "Kampanye",        roles: ["admin", "manager", "designer", "sales", "sales_admin"] },
    { view: "mkt-accounts",  label: "Akun Sosmed",     roles: ["admin", "manager", "designer", "sales", "sales_admin"] },
  ],
  // PS-18 — hub DESAINER (terpisah dari R&D): orang + karyanya.
  "designer-hub": [
    // FASE D — papan pekerjaan desain (penugasan · tenggat · keputusan). Ditaruh
    // PALING DEPAN karena inilah pintu kerja harian peran `designer`.
    { view: "design-requests",   label: "Permintaan Desain",  roles: ["admin", "manager", "designer"] },
    { view: "designer-kpi",      label: "KPI Desainer",       roles: ["admin", "manager"] },
    { view: "rnd-designs",       label: "Desain & Pattern",   roles: ["admin", "manager", "designer"] },
    { view: "cs-design-gallery", label: "Galeri Desain (Showcase)", roles: ["admin", "manager"] },
    { view: "rnd-divisions",     label: "Divisi & Persetujuan", roles: ["admin", "manager"] },
  ],
  "wms-operations": [
    { view: "operations",        label: "Stok, Transfer & Opname", roles: ["admin", "warehouse", "manager", "sales"] },
    // 2026-10 — Barang Masuk & Barang Keluar SATU LEVEL (dulu Barang Keluar tab di dalam Operasi WMS).
    { view: "goods-receipts",    label: "Barang Masuk",          roles: ["admin", "warehouse", "manager", "warehouse_admin", "finance"] },
    { view: "wms-outbound",      label: "Barang Keluar",         roles: ["admin", "warehouse", "manager", "sales"] },
    { view: "qc-inspection",     label: "Antrean QC Kedatangan", roles: ["admin", "warehouse", "manager"] },
    // FASE I — dokumen inspeksi (SPK): siapa memeriksa, atas dasar sample mana, dan
    // keputusannya. Ditaruh SESUDAH "Inspeksi QC" (antrean karantina) karena itulah
    // urutan kerjanya: barang masuk antrean \u2192 SPK-nya lahir \u2192 hasil & keputusan.
    { view: "inspections",       label: "Dokumen Inspeksi (INS)", roles: ["admin", "warehouse", "manager"] },
    { view: "interco-transfers", label: "Transfer Antar-Entitas", roles: ["admin", "warehouse", "manager"] },
  ],
  "stock-atp": [
    { view: "inventory-board",   label: "Status Stok & ATP",     roles: ["admin", "warehouse", "manager", "sales"] },
    { view: "stock-buckets",     label: "Stok Multi-Bucket",     roles: ["admin", "warehouse", "manager"] },
    { view: "inventory-lots",    label: "Lot & Silsilah",        roles: ["admin", "warehouse", "manager", "sales"] },
  ],
  "cash-bank": [
    { view: "bank-accounts",     label: "Rekening & Saldo",      roles: ["admin", "manager"] },
    { view: "cash-management",   label: "Transaksi Kas",         roles: ["admin", "manager"] },
    { view: "bank-reconciliation", label: "Rekonsiliasi Bank",   roles: ["admin", "manager"] },
  ],
  "petty-cash": [
    { view: "cash-advances",      label: "Pengajuan Dana (PD)",  roles: ["admin", "manager", "sales"] },
    { view: "settlements",        label: "Pertanggungjawaban",   roles: ["admin", "manager", "sales"] },
    { view: "reimburse-payables", label: "Hutang Reimburse",     roles: ["admin", "manager"] },
    { view: "expense-categories", label: "Kategori Beban",       roles: ["admin", "manager"] },
  ],
  "tax-hub": [
    { view: "tax-invoices",      label: "Faktur Keluaran",       roles: ["admin", "manager"] },
    { view: "input-tax",         label: "Faktur Masukan",        roles: ["admin", "manager"] },
    { view: "cs-pajak",          label: "PPh & Rekap",           roles: ["admin", "manager"] },
  ],
  "ledger": [
    { view: "general-ledger",    label: "Jurnal & Buku Besar",   roles: ["admin", "manager"] },
    { view: "chart-of-accounts", label: "Chart of Accounts",     roles: ["admin", "manager"] },
  ],
  "fin-reports": [
    { view: "financial-statements", label: "Laba-Rugi, Neraca & Arus Kas", roles: ["admin", "manager"] },
    { view: "profitability",        label: "Profitabilitas & Margin",       roles: ["admin", "manager"] },
    { view: "cashflow-forecast",    label: "Proyeksi Arus Kas",             roles: ["admin", "manager"] },
    { view: "budget",               label: "Anggaran vs Realisasi",         roles: ["admin", "manager"] },
    { view: "consolidation",        label: "Konsolidasi Grup",              roles: ["admin", "manager"] },
  ],
  "hr-people": [
    { view: "hr-employees",      label: "Karyawan",              roles: ["admin", "manager"] },
    { view: "hr-org-units",      label: "Struktur Organisasi",   roles: ["admin", "manager"] },
  ],
  "hr-attendance-hub": [
    { view: "hr-attendance",       label: "Presensi",            roles: ["admin", "manager"] },
    { view: "hr-leave",            label: "Cuti & Izin",         roles: ["admin", "manager"] },
    { view: "hr-overtime",         label: "Lembur",              roles: ["admin", "manager"] },
    { view: "hr-live-tracking",    label: "Lacak Lapangan",      roles: ["admin", "manager"] },
    { view: "hr-attendance-setup", label: "Shift & Geofence",    roles: ["admin", "manager"] },
  ],
  "hr-payroll-hub": [
    { view: "hr-payroll-runs",   label: "Payroll Run",           roles: ["admin", "manager"] },
    { view: "hr-payslips",       label: "Slip Gaji",             roles: ["admin", "manager"] },
    // FASE G-0 — "Setup Penggajian" DIHAPUS. Semua aturan BPJS/PPh21/lembur kini
    // hanya ada di Pusat Pengaturan (kelompok "SDM & Penggajian"). Manager tetap
    // berwenang mengubahnya lewat izin hr.manage_payroll — tidak ada wewenang hilang.
  ],
  "hr-kpi-hub": [
    { view: "cs-kpi",            label: "KPI Karyawan (manual)", roles: ["admin", "manager"] },
  ],
  "analytics": [
    { view: "reports",           label: "Ringkasan",              roles: ["admin", "manager"] },
    { view: "costing",           label: "Margin & HPP",          roles: ["admin", "manager"] },
    { view: "cs-bi-hrd",         label: "BI SDM",                roles: ["admin", "manager"] },
    // 2026-10 — dipindah dari grup Gudang: semua analitik di satu hub.
    { view: "cs-stock-analytics", label: "Analitik Stok",         roles: ["admin", "manager", "warehouse_admin"] },
  ],
  // FASE G-4 — Pusat Dokumen menjadi hub: daftar dokumen + Jejak Dokumen (relasi surat).
  "document-center": [
    { view: "document-center", label: "Daftar Dokumen",  roles: ["admin", "sales", "manager", "warehouse"] },
    { view: "doc-trace",       label: "Jejak Dokumen",   roles: ["admin", "sales", "manager", "warehouse"] },
    // 2026-10 — "Pusat Cetak" (menu terpisah) digabung ke sini: satu pintu dokumen.
    { view: "documents",       label: "Cetak PDF & Label", roles: ["admin", "sales", "manager", "warehouse"] },
  ],
  // IA 2026-10 (B11) — dua dasbor keuangan dalam satu pintu.
  "finance-tower": [
    { view: "finance-tower",     label: "Posisi & Kontrol",      roles: ["admin", "manager"] },
    { view: "bi-finance",        label: "BI Keuangan",           roles: ["admin", "manager"] },
  ],
  // IA 2026-10 (D1) — RFID jadi satu hub di grup Gudang (dulu grup sendiri, 4 menu).
  "rfid-hub": [
    { view: "cs-rfid-lokasi",    label: "Lokasi RFID",           roles: ["admin", "warehouse"] },
    { view: "cs-rfid-tags",      label: "Tag RFID",              roles: ["admin", "warehouse"] },
    { view: "cs-rfid-devices",   label: "Perangkat",             roles: ["admin"] },
    { view: "cs-rfid-gate",      label: "Monitor Gerbang",       roles: ["admin", "warehouse"] },
  ],
  // IA 2026-10 (D3) — 3 seksi: Sistem · Organisasi & Akses · Kamus & Dokumen.
  "settings-hub": [
    { view: "settings-config",   label: "Pusat Pengaturan",      roles: ["admin", "manager"], section: "Sistem" },
    { view: "scheduler",         label: "Penjadwal & Notifikasi", roles: ["admin", "manager"], section: "Sistem" },
    { view: "admin",             label: "Integrasi & Audit",     roles: ["admin"], section: "Sistem" },
    { view: "entities-access",   label: "Badan Usaha & Akses",   roles: ["admin", "manager"], section: "Organisasi & Akses" },
    // B2 — matriks izin semua peran berdampingan (dulu tab "Hak Akses" di Master Data & Audit).
    { view: "permission-matrix", label: "Matriks Izin",          roles: ["admin"], section: "Organisasi & Akses" },
    { view: "approval-rules",    label: "Aturan Persetujuan",    roles: ["admin"], section: "Organisasi & Akses" },
    // master BERLAPIS global → badan usaha (override per BU; editor lengkap ada di domainnya).
    { view: "entity-masters",    label: "Master per Badan Usaha", roles: ["admin", "manager"], section: "Organisasi & Akses" },
    { view: "domain-registry",   label: "Registri Domain",       roles: ["admin", "manager"], section: "Kamus & Dokumen" },
    { view: "pdf-templates",     label: "Template PDF",          roles: ["admin"], section: "Kamus & Dokumen" },
    // B3 — template dokumen dasar: kertas/orientasi/urutan bagian (dulu tab di Master Data & Audit).
    { view: "doc-templates-basic", label: "Template Dokumen Dasar", roles: ["admin"], section: "Kamus & Dokumen" },
    // 2026-10 — Profil SJ · Sampel Uji OCR · Biaya OCR · Mode Penerimaan (dulu tab di Barang Masuk).
    { view: "settings-receiving-ocr", label: "Penerimaan & OCR", roles: ["admin", "manager", "warehouse_admin"], section: "Gudang" },
  ],
};

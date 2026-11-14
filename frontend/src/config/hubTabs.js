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
    // Fase 3 · P8 (D-06) — "Persetujuan Saya" kini tab "Matriks divisi" di dalam Pusat Persetujuan (alias `my-approvals`
    // → {tab:"matrix"} di viewAliases.js; rute cadangan tetap). Tab hub-nya dicabut.
    { view: "price-approvals",   label: "Pengajuan Harga Khusus",   roles: ["admin", "sales", "manager"] },
    { view: "purchase-approval", label: "Persetujuan Pembelian",    roles: ["admin", "manager"] },
  ],
  "sales-orders": [
    { view: "orders",            label: "Pesanan (SO)",          roles: ["admin", "sales", "manager"] },
    // UAT 24 Okt (P13.3) — Keep & Pending dulu hanya kartu di Beranda; sales melihat SO MILIKNYA saja (server).
    { view: "keep-pending",      label: "Keep & Pending",        roles: ["admin", "sales", "manager"] },
    { view: "amendments",        label: "Koreksi & Amandemen",   roles: ["admin", "sales", "manager"] },
    // L08 — "Retur & Barang Sisa" PINDAH ke menu tunggal "Retur" (hub returns-hub).
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
    // Harga: dua lapis dalam SATU tempat — harga per PT lalu harga khusus pelanggan.
    { view: "pricelist",         label: "Harga per PT",          roles: ["admin", "manager"] },
    { view: "cs-price-list",     label: "Harga per Pelanggan",   roles: ["admin", "manager", "sales"] },
    { view: "internal-prices",   label: "Harga Internal Antar-PT", roles: ["admin"] },
    // Fase 3 · P2 (P16-K1) — Koreksi Harga & Daftar Dampak (dulu tab di Pusat Pengaturan). Manajer: pratinjau dampak
    // (server: product.view); menerapkan tetap product.update.
    { view: "price-corrections", label: "Koreksi Harga",         roles: ["admin", "manager"] },
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
    // Fase 3 · P8 (D-22) — satu layar Kinerja Mitra Makloon (rekap susut & klaim + skor mitra). + warehouse: gudang dulu
    // melihat skor mitra di Klaim Selisih Makloon; tanpa izin rekap layar menampilkan skor saja (403 ditangani layar).
    { view: "makloon-claim-recap", label: "Kinerja Mitra Makloon", roles: ["admin", "manager", "finance", "md", "warehouse"] },
    { view: "makloon-claims",    label: "Klaim Selisih Makloon", roles: ["admin", "manager", "warehouse"] },
    // MN-T1 — dari Hutang Pemasok: pembebanan biaya ke barang PO, bukan hutang (view sama). Hub ini 7 tab tampak —
    // tercatat di baseline INV-UI-13 (`scripts/guardrails/baselines/hub_tab_limit.json`), bukan pelonggaran.
    { view: "landed-cost",       label: "Landed Cost",           roles: ["admin", "manager"] },
  ],
  "master-pembelian": [
    { view: "suppliers",         label: "Pemasok (Supplier)",    roles: ["admin", "manager"] },
    { view: "makloons",          label: "Mitra Makloon",         roles: ["admin", "manager"] },
    { view: "supplier-contracts", label: "Kontrak Mitra & Supplier", roles: ["admin", "manager", "warehouse"] },
    { view: "supplier-items",    label: "Barang Supplier",       roles: ["admin", "manager", "warehouse"] },
    // Fase 3 · P8 (D-25) — nama diperjelas (beda dengan BOM Produksi In-House di Gudang).
    { view: "process-recipes",   label: "Resep Proses Makloon",  roles: ["admin", "manager"] },
    // Fase 3 · P8 (D-23) — Harga Internal Antar-PT untuk peran Kontrak yang tak punya tab Produk & Harga › Harga
    // Internal (tautan "Isi massal"/"Harga Internal" di Kontrak). Layar sama (`InternalPricesView`); izin tulis dari
    // server (`interco_price`).
    { view: "supplier-internal-prices", label: "Harga Internal Antar-PT", roles: ["admin", "manager", "warehouse"], hidden: true, aliasOf: "supplier-contracts" },
  ],
  // MN-T1 — Keuangan › Hutang (dulu Pembelian › Hutang Pemasok). Finance lewat ROLE_NAV (K-17: lihat & bayar).
  "accounts-payable": [
    { view: "vendor-bills",      label: "Tagihan",               roles: ["admin", "manager"] },
    // FASE G-7 — kontrabon: satu siklus tukar faktur = satu tanda terima + satu
    // pembayaran. Gudang ikut MELIHAT karena tab "GR Belum Ditagih" adalah pekerjaan
    // mereka (barang sudah diterima tapi faktur supplier belum datang).
    { view: "contra-bons",       label: "Kontrabon",             roles: ["admin", "manager", "warehouse"] },
    // PK-28 (IV-03) — sisa GR/IR per PO + umur + kliring. Finance lewat ROLE_NAV (lihat; kliring butuh accounting.manage).
    { view: "gr-ir",             label: "GR/IR (Diterima Belum Ditagih)", roles: ["admin", "manager"] },
    // MN-T1 — Landed Cost PINDAH ke Pembelian › Pesanan Pembelian (view sama).
  ],
  // L08 LN-080 — menu Retur terpadu: semua arah retur di satu tempat (tiap tab = layar aslinya).
  "returns-hub": [
    // F-11-layar (keputusan pemilik 2026-10-21) — Gudang menscan terima/kirim/tiba & QC memeriksa:
    // server memberi mereka daftar approved/inspecting tanpa field uang (bukan `sales_return.view`).
    // 23 Okt — Admin Sales = pemutus bawaan terima/tolak per roll (`sales_return.decide_rolls`).
    // UAT 23 Okt — + MD & MD Quality: cutloss (catat qty cacat, pecah roll) dikerjakan di detail retur.
    { view: "returns",           label: "Retur Pelanggan",       roles: ["admin", "sales", "sales_admin", "manager", "warehouse", "qc", "md", "md_quality"] },
    { view: "interco-returns",   label: "Retur Antar-PT",        roles: ["admin", "manager", "warehouse", "finance", "sales_admin"] },
    { view: "purchase-returns",  label: "Retur ke Supplier (Nota Debit)", roles: ["admin", "manager", "warehouse"] },
    // Fase 3 · P2 (P16-K1) — "Kebijakan Retur" pindah ke Pengaturan › Penjualan (view id sama).
  ],
  // FASE F — R&D: hulu rantai (spesifikasi → labdip/proofing → kontrak).
  // warehouse ikut melihat karena dialah yang mengeluarkan bahan sample (PS-19).
  // CATATAN IA (PS-18): "Desain & Pattern" DIPINDAH ke hub `designer-hub` supaya
  // urusan desainer tidak lagi bercampur dengan proses R&D.
  "rnd-hub": [
    // "Spesifikasi Produk" DIKONSOLIDASIKAN ke form Permintaan Sample (bagian 3) & panel
    // "Master data" di rincian sample — tab terpisah dihapus (permintaan pemilik 2026-09).
    // UAT 24 Okt (P4.1, permintaan pemilik) — DUA PINTU: produk baru (handfeel → labdip → produk) & uji ulang SKU.
    { view: "rnd-samples", label: "R&D Produk Baru",  roles: ["admin", "manager", "sales", "warehouse", "md", "sales_admin"] },
    { view: "rnd-revalidation", label: "Uji Ulang", roles: ["admin", "manager", "sales", "warehouse", "md", "sales_admin"] },
    // 23 Okt — tab tetap TIDAK tampil (keputusan pemilik di atas), tetapi alamatnya hidup kembali sebagai alias
    // tersembunyi: antrean "Spesifikasi produk menunggu ACC" (dasbor/Pusat Persetujuan Manajer) & Jejak Dokumen
    // menautkan ke `rnd-specs` — dulu tautan itu melempar pengguna ke Beranda.
    { view: "rnd-specs", label: "Spesifikasi Produk", roles: ["admin", "manager", "sales", "md", "sales_admin"], hidden: true, aliasOf: "rnd-samples" },
    // Fase 3 · P8 (D-24b, keputusan pemilik 26 Okt) — tab Labdip/Handfeel/Proofing dicabut: galeri per jenis = mode
    // Galeri + chip jenis di R&D Produk Baru (alias `rnd-labdip` dkk. → `rnd-samples` {mode:"gallery", type}).
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
    // Fase 3 · P8 (D-09) — Galeri Desain (Showcase) = mode Galeri di Desain & Pattern (alias `cs-design-gallery`).
  ],
  "wms-operations": [
    { view: "operations",        label: "Stok, Transfer & Opname", roles: ["admin", "warehouse", "manager", "sales"] },
    // 2026-10 — Barang Masuk & Barang Keluar SATU LEVEL (dulu Barang Keluar tab di dalam Operasi WMS).
    { view: "goods-receipts",    label: "Barang Masuk",          roles: ["admin", "warehouse", "manager", "warehouse_admin", "finance"] },
    { view: "wms-outbound",      label: "Barang Keluar",         roles: ["admin", "warehouse", "manager", "sales"] },
    // Trial 22 Okt (F1) — operasi potong (sample/catalogue + potong roll SO) DIPISAH dari Barang Keluar (order biasa).
    { view: "wms-cutting",       label: "Cutting",               roles: ["admin", "warehouse", "manager", "warehouse_admin"] },
    // UAT 24 Okt (P7) — roll cacat / warna meleset diperbaiki, dicelup ulang, atau di-finishing ulang lalu kembali ke stok.
    { view: "repair-orders",     label: "Perbaikan",             roles: ["admin", "warehouse", "manager", "warehouse_admin", "md"] },
    // 2026-10 (T5.2) — Transfer Antar-PT kini sub-tab di "Stok, Transfer & Opname" › Transfer.
    { view: "interco-transfers", label: "Transfer Antar-PT", roles: ["admin", "warehouse", "manager"], hidden: true, aliasOf: "operations" },
  ],
  // 23 Okt (IA, keputusan pemilik) — KUALITAS menu tersendiri (pola SAP QM / Odoo Quality): satu rumah untuk antrean
  // QC kedatangan & SPK inspeksi SEMUA sumber (penerimaan PO, makloon, retur pelanggan/supplier, random check).
  // Dulu tab "QC & Inspeksi" di Operasi Gudang dengan sub-tab di dalamnya (tab-dalam-tab).
  "quality-hub": [
    { view: "qc-inspection",     label: "Antrean QC Kedatangan", roles: ["admin", "warehouse", "manager"] },
    { view: "inspections",       label: "SPK Inspeksi",          roles: ["admin", "warehouse", "manager"] },
  ],
  "stock-atp": [
    { view: "inventory-board",   label: "Status Stok & ATP",     roles: ["admin", "warehouse", "manager", "sales"] },
    { view: "stock-buckets",     label: "Stok Multi-Bucket",     roles: ["admin", "warehouse", "manager"] },
    { view: "inventory-lots",    label: "Lot & Silsilah",        roles: ["admin", "warehouse", "manager", "sales"] },
  ],
  "cash-bank": [
    { view: "bank-accounts",     label: "Rekening & Saldo",      roles: ["admin", "manager"] },
    { view: "cash-management",   label: "Transaksi Kas",         roles: ["admin", "manager"] },
    { view: "bank-reconciliation", label: "Rekonsiliasi",        roles: ["admin", "manager"] },
    // MN-T1 — Kas Kecil (dulu hub Kas & Aset › Kas Kecil, 3 tab) = satu tab pembungkus ber-chip (PettyCashView):
    // Pengajuan dana · Pertanggungjawaban · Hutang reimburse. Id lama = alias (viewAliases.js) + rute cadangan.
    { view: "petty-cash",        label: "Kas Kecil",             roles: ["admin", "manager", "sales"] },
  ],
  "tax-hub": [
    { view: "tax-invoices",      label: "Faktur Keluaran",       roles: ["admin", "manager"] },
    { view: "input-tax",         label: "Faktur Masukan",        roles: ["admin", "manager"] },
    { view: "cs-pajak",          label: "PPN & PPh",             roles: ["admin", "manager"] },
  ],
  "ledger": [
    { view: "general-ledger",    label: "Jurnal",                roles: ["admin", "manager"] },
    { view: "chart-of-accounts", label: "Bagan Akun",            roles: ["admin", "manager"] },
  ],
  "fin-reports": [
    { view: "financial-statements", label: "Laba-Rugi, Neraca & Arus Kas", roles: ["admin", "manager"] },
    { view: "profitability",        label: "Profitabilitas",                roles: ["admin", "manager"] },
    { view: "cashflow-forecast",    label: "Proyeksi Kas",                  roles: ["admin", "manager"] },
    { view: "budget",               label: "Anggaran",                      roles: ["admin", "manager"] },
    { view: "consolidation",        label: "Konsolidasi",                   roles: ["admin", "manager"] },
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
  ],
  "hr-payroll-hub": [
    { view: "hr-payroll-runs",   label: "Proses Gaji",           roles: ["admin", "manager"] },
    { view: "hr-payslips",       label: "Slip Gaji",             roles: ["admin", "manager"] },
    // PK-22 (FY-07) — setoran hutang BPJS & PPh 21 (izin bayar `payroll.pay`; lihat `hr.view`).
    { view: "hr-payroll-remittances", label: "Setoran Kewajiban", roles: ["admin", "manager"] },
    // FASE G-0 — "Setup Penggajian" DIHAPUS. Semua aturan BPJS/PPh21/lembur kini
    // hanya ada di Pusat Pengaturan (kelompok "SDM & Penggajian"). Manager tetap
    // berwenang mengubahnya lewat izin hr.manage_payroll — tidak ada wewenang hilang.
  ],
  // MN-T1 — SDM › Kinerja & Insentif: Kinerja Sales & Skema (dulu sub-tab CRM) + Target & Aturan (dulu Pengaturan ›
  // Penjualan › Komisi & Insentif) + KPI Karyawan. Komponen lama dirender tanpa perubahan.
  "hr-kpi-hub": [
    { view: "sales-performance", label: "Kinerja Sales",         roles: ["admin", "manager", "sales"] },
    // D-03 — tarif per kategori + bawaan komisi (`commission.*`) di satu layar (view sama).
    { view: "incentive-rates",   label: "Target & Aturan",       roles: ["admin", "manager"] },
    { view: "incentive-schemes", label: "Skema (Arsip)",         roles: ["admin", "manager"] },
    { view: "cs-kpi",            label: "KPI Karyawan",          roles: ["admin", "manager"] },
  ],
  "analytics": [
    { view: "reports",           label: "Ringkasan",              roles: ["admin", "manager"] },
    // Fase 3 · P8 (D-11) — Margin & HPP = tab "Margin katalog" di Akuntansi & Pajak › Laporan › Profitabilitas & Margin
    // (alias `costing` → `profitability` {tab:"katalog"}).
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
  // IA 2026-10 (B11) — dua dasbor keuangan dalam satu pintu. MN-T1 — "Beranda Keuangan": + Meja Finance sebagai tab
  // pertama "Perlu Tindakan" (dulu menu lepas & butir Meja Peran). Finance lewat ROLE_NAV.
  "finance-tower": [
    { view: "finance-desk",      label: "Perlu Tindakan",        roles: ["admin", "manager"] },
    { view: "finance-tower",     label: "Posisi",                roles: ["admin", "manager"] },
    { view: "bi-finance",        label: "Analisis",              roles: ["admin", "manager"] },
  ],
  // MN-T1 — Keuangan › Piutang (dulu satu layar + 4 entri Keuangan + 2 sub-tab CRM). Menagih = sales juga.
  "ar-aging": [
    { view: "ar-aging",          label: "Saldo & Umur",          roles: ["admin", "manager"] },
    { view: "collection-worklist", label: "Penagihan & Penerimaan", roles: ["admin", "manager", "sales"] },
    { view: "payment-plans",     label: "Rencana & Denda",       roles: ["admin", "manager"] },
    // Pembungkus Uang Muka Pelanggan + Saldo Kredit (CustomerCreditView); id lama = alias + rute cadangan.
    { view: "customer-credit",   label: "Titipan & Saldo Kredit", roles: ["admin", "manager"] },
    // Persetujuan Kredit (dulu sub-tab CRM): daftar = `customer.view`; tombol memutus = `credit_override.approve`.
    { view: "credit-overrides",  label: "Kredit & Plafon",       roles: ["admin", "manager"] },
    // FASE G-9 — sales boleh MELAPOR & memantau (finance_case: view+create), tidak menutup kasus uang.
    { view: "finance-cases",     label: "Kasus",                 roles: ["admin", "manager", "sales"] },
  ],
  // MN-T1 — Akuntansi & Pajak › Tutup Buku (dulu tiga entri terpisah).
  "closing": [
    { view: "closing",           label: "Daftar Periksa & Tutup", roles: ["admin", "manager"] },
    { view: "period-unlock",     label: "Buka Periode",          roles: ["admin", "manager"] },
    { view: "posting-failures",  label: "Posting Gagal",         roles: ["admin", "manager"] },
  ],
  // IA 2026-10 (D1) — RFID jadi satu hub di grup Gudang (dulu grup sendiri, 4 menu).
  "rfid-hub": [
    // FIX-1 (K-B1-07 diputuskan) — manajer diberi menu RFID (baca; aksi dijaga izin server).
    { view: "cs-rfid-lokasi",    label: "Lokasi RFID",           roles: ["admin", "warehouse", "manager"] },
    { view: "cs-rfid-tags",      label: "Tag RFID",              roles: ["admin", "warehouse", "manager"] },
    { view: "cs-rfid-gate",      label: "Monitor Gerbang",       roles: ["admin", "warehouse", "manager"] },
  ],
  // ── PENGATURAN — KP-T9 (K-46): SEMBILAN hub berurutan menurut cara mengisi PT baru — PT → orang → persetujuan → aturan
  // per bagian → dokumen → sistem. Dulu (fase 3 · P2, P16-K1) 12 hub dengan tiga hub ber-tab tunggal dan enam layar wadah
  // ber-tab-dalam. Editor lama TETAP memakai view id-nya (deep link, notifikasi, katalog akses); hub yang hilang
  // (`settings-purchasing`, `settings-rnd`, `settings-masters`, `settings-notify`) = alias legacy (viewAliases.js).
  // Bagian layar wadah yang dinaikkan menjadi tab hub (`settings-pt-*`, `settings-accounts`, `settings-role-check`,
  // `settings-attendance-devices`, `settings-whatsapp`) merender komponen yang sama dengan prop `only` (AppViewRouter) dan
  // membawa `inheritsHiddenFrom`: tersembunyi bila id wadah lamanya ada di `hidden_views` peran (navigationConfig).
  // `roles` tiap tab = `roles` tab/bagian lamanya. "Cari Semua Pengaturan" (`settings-config`) tetap satu-satunya tempat
  // cari lintas kelompok, riwayat, kesehatan, kunci proses & kebersihan data (Q6) — WAJIB di menu (audit_config_wiring).
  "settings-company": [
    // Bagian "Badan Usaha" dan "Kesiapan" layar Badan Usaha & Akses (`entities-access` = alias ke Profil PT).
    { view: "settings-pt-profile",   label: "Profil PT",     roles: ["admin", "manager"], inheritsHiddenFrom: "entities-access" },
    { view: "settings-pt-readiness", label: "Kesiapan PT",   roles: ["admin", "manager"], inheritsHiddenFrom: "entities-access" },
    // master BERLAPIS global → PT; jenis yang punya rumah domain tampil sebagai TAUTAN (D-01..D-04). Dulu hub Master Data.
    { view: "entity-masters",        label: "Master per PT", roles: ["admin", "manager"] },
  ],
  "settings-access": [
    // Bagian "Akun & Akses", "Peran & Hak Akses" (dulu juga alias tersembunyi `permission-matrix`), "Cek Peran".
    { view: "settings-accounts",   label: "Akun",              roles: ["admin", "manager"], inheritsHiddenFrom: "entities-access" },
    { view: "permission-matrix",   label: "Peran & Hak Akses", roles: ["admin", "manager"], inheritsHiddenFrom: "entities-access" },
    { view: "settings-role-check", label: "Cek Peran",         roles: ["admin", "manager"], inheritsHiddenFrom: "entities-access" },
  ],
  "settings-approval": [
    // D-04 — manajer membaca aturan (dulu lewat Master per PT); tombol ubah hanya bagi izin settings.manage.
    { view: "approval-rules",    label: "Aturan Persetujuan",    roles: ["admin", "manager"] },
    // Matriks approver R&D (DivisionsView bagian "matriks"); penempatan tim di Gudang, Pembelian & Produksi › R&D & Desain.
    { view: "rnd-divisions",     label: "Persetujuan R&D",       roles: ["admin", "manager"] },
    { view: "settings-cfg-approval", label: "Ketegasan, Pengingat & Dokumen", roles: ["admin", "manager"] },
    // KF-T6 — satu tabel aturan "pengaju tidak boleh memutuskan sendiri" per PT (GET /api/kontrol/aturan).
    { view: "settings-dual-control", label: "Kontrol dua orang", roles: ["admin", "manager"] },
  ],
  "settings-sales": [
    { view: "settings-cfg-sales", label: "Aturan Penjualan",     roles: ["admin", "manager"] },
    // MN-T1 — "Komisi & Insentif" pindah ke SDM › Kinerja & Insentif › Target & Aturan (view sama).
    // P16-K1 — dipindah dari hub Retur (sales_admin tetap lewat ROLE_NAV `return-policies` + `settings-sales`).
    { view: "return-policies",   label: "Kebijakan Retur",       roles: ["admin", "manager"] },
    { view: "amendment-reasons", label: "Alasan Koreksi",        roles: ["admin", "manager"] },
  ],
  "settings-warehouse": [
    { view: "settings-cfg-warehouse", label: "Aturan Gudang & Mutu", roles: ["admin", "manager"] },
    // 2026-10 — Profil SJ · Sample Uji OCR · Biaya OCR · Mode Penerimaan (dulu tab di Barang Masuk).
    { view: "settings-receiving-ocr", label: "Penerimaan Barang", roles: ["admin", "manager", "warehouse_admin"] },
    { view: "grade-master",      label: "Grade Mutu",            roles: ["admin", "manager", "md", "sales_admin", "warehouse_admin", "md_quality", "qc"] },
    // KP-T9 — dulu hub ber-tab tunggal Pembelian & Produksi dan R&D (`settings-purchasing`, `settings-rnd` = alias).
    { view: "settings-cfg-purchasing", label: "Aturan Pembelian & Makloon", roles: ["admin", "manager"] },
    // Aturan R&D (kelompok registri `rnd`) + penempatan tim R&D (bagian "tim" DivisionsView).
    { view: "settings-cfg-rnd",  label: "R&D & Desain",          roles: ["admin", "manager"] },
  ],
  "settings-finance": [
    { view: "settings-cfg-finance", label: "Aturan Keuangan & Pajak", roles: ["admin", "manager"] },
    { view: "gl-account-mappings", label: "Pemetaan Akun",       roles: ["admin", "manager", "finance"] },
    // D-02 — satu editor kategori (lapis global → PT + pemilih akun COA).
    { view: "expense-categories", label: "Kategori Beban",        roles: ["admin", "manager"] },
    { view: "bank-recon-rules",  label: "Bank",                  roles: ["admin", "manager"] },
  ],
  "settings-hr": [
    { view: "settings-cfg-hr",   label: "Aturan SDM & Penggajian", roles: ["admin", "manager"] },
    { view: "hr-attendance-setup", label: "Shift & Lokasi Absen", roles: ["admin", "manager"] },
    // Bagian "Mesin absen" layar Perangkat (D-29). Juga ikut tersembunyi bila Shift & Lokasi Absen disembunyikan — gerbang
    // bagian itu di layar lama (`DevicesView`) memakai id `hr-attendance-setup`.
    { view: "settings-attendance-devices", label: "Mesin Absen", roles: ["admin", "manager"], inheritsHiddenFrom: ["settings-devices", "hr-attendance-setup"] },
  ],
  "settings-documents": [
    // D-01 — Template PDF + Template Dokumen Dasar digabung (alias `doc-templates-basic` → tab "dasar").
    // Tab "Desainer PDF" di dalam layar tetap khusus admin; hak tulis dijaga server (izin `template`).
    { view: "pdf-templates",     label: "Template Dokumen",      roles: ["admin", "manager"] },
    // KP-T9 — bagian "Job Terjadwal" + "Riwayat Eksekusi" layar Penjadwal & Notifikasi (dulu hub `settings-notify`).
    { view: "scheduler",         label: "Pengingat Otomatis",    roles: ["admin", "manager"] },
    { view: "settings-whatsapp", label: "WhatsApp",              roles: ["admin", "manager"], inheritsHiddenFrom: "scheduler" },
    // KP-T5 — format nomor dokumen per jenis per PT (GET /api/doc-numbering = settings.view; ubah settings.manage).
    { view: "settings-doc-numbering", label: "Penomoran Dokumen", roles: ["admin", "manager"] },
    // KF-T4 — tab "Aturan Dokumen" & "Penerima Notifikasi" dicabut: sub-judul di Persetujuan (alias viewAliases).
  ],
  "settings-system": [
    { view: "admin",             label: "Integrasi & Audit",     roles: ["admin"] },
    // Bagian "RFID" layar Perangkat (D-29; alias `cs-rfid-devices`). Khusus admin seperti bagian RFID dulu (gerbang
    // `roleCanSee(["admin"], role, "cs-rfid-devices")`); peran kustom lewat modul Operasi Gudang / Perangkat.
    { view: "settings-devices",  label: "Perangkat RFID",        roles: ["admin"], inheritsHiddenFrom: "cs-rfid-devices" },
    { view: "domain-registry",   label: "Kamus Aturan Kain",     roles: ["admin", "manager"] },
    { view: "client-dataset-import", label: "Impor Data Awal",   roles: ["admin"] },
    { view: "settings-cfg-system", label: "AI & Tampilan",       roles: ["admin", "manager"] },
    // Q6 — Pusat Pengaturan penuh (cari lintas kelompok, kesehatan, riwayat, kunci proses, kebersihan data).
    { view: "settings-config",   label: "Cari Semua Pengaturan", roles: ["admin", "manager"] },
  ],
};

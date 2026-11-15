// ─── NAV STRUCTURE DATA (hub-and-tab IA) + HUB TABS ──────────────────────────
// Dipisah dari navigationConfig.js agar file config di bawah batas guardrail.
import {
  AlertTriangle,
  Megaphone,
  Sparkles,
  Scissors,
  BarChart3,
  Bell,
  Boxes,
  Briefcase,
  Calculator,
  CalendarX,
  Truck,
  Clock,
  CreditCard,
  Cpu,
  DollarSign,
  FileText,
  FileStack,
  FileBarChart,
  Home,
  IdCard,
  Landmark,
  Layers3,
  MapPin,
  Palette,
  Percent,
  PieChart,
  Printer,
  Receipt,
  Settings,
  ShoppingBag,
  ShoppingCart,
  Target,
  TrendingDown,
  UserCheck,
  Users,
  Warehouse,
  ClipboardList,
  Factory,
  FlaskConical,
  Car,
  ReceiptText,
  FolderTree,
  BellRing,
  FileSpreadsheet,
  RotateCcw,
  ShieldCheck,
  Building2,
  UserCog,
} from "lucide-react";

// HUB TABS (tab per hub) dipindah ke `hubTabs.js` — re-export agar impor lama tetap jalan.
export { HUB_TABS } from "./hubTabs";

// ─── NAV STRUCTURE (IA v2 — hub-and-tab, 7±2 per grup, urutan = alur proses) ──
export const NAV_STRUCTURE = [

  // ── BERANDA ──────────────────────────────────────────────────────────────────
  {
    type: "standalone",
    id:    "home",
    label: "Beranda",
    icon:  Home,
    roles: ["admin", "sales", "manager", "warehouse"],
    view:  null,  // App.js resolve via defaultViewForRole
  },

  // ── PUSAT PERSETUJUAN (satu pintu semua approval) ────────────────────────────
  {
    type: "standalone",
    id:    "approval-inbox",
    label: "Pusat Persetujuan",
    icon:  Bell,
    roles: ["manager", "admin", "sales"],
    hub:   "approval-inbox",
  },

  // ── MEJA KERJA PERAN (FASE E-8 · E8.7/E8.20) ────────────────────────────────
  // Dua peran baru bekerja dari ANTREAN, bukan dari daftar dokumen. Karena itu
  // mejanya berada di puncak menu (setara "Pusat Persetujuan" milik manajer),
  // bukan terkubur di dalam grup: ia layar pertama yang dibuka tiap pagi.
  // `roles: ["admin"]` saja — dua peran baru mendapatkannya lewat overlay
  // `ROLE_NAV` di `config/roles.js` (lihat alasannya di berkas itu).
  // U-2 (2026-09) — Meja Saya untuk admin, manager, sales, warehouse, designer, driver.
  {
    type: "standalone",
    id:    "my-desk",
    label: "Meja Saya",
    icon:  BellRing,
    roles: ["admin", "manager", "sales", "warehouse", "designer", "driver"],
    view:  "my-desk",
  },
  // ── TANYA KN (asisten analitik: template laporan + chat) ─────────────────────
  {
    type: "standalone",
    id:    "tanya-kn",
    label: "Tanya KN",
    icon:  Sparkles,
    roles: ["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales"],
    view:  "tanya-kn",
  },
  {
    type: "standalone",
    id:    "sales-admin-desk",
    label: "Meja Admin Sales",
    icon:  ClipboardList,
    roles: [],
    view:  "sales-admin-desk",
  },
  // MN-T1 — "Meja Finance" bukan lagi menu lepas: kini tab "Perlu Tindakan" di Keuangan › Beranda Keuangan (view tetap
  // `finance-desk`; peran Finance tetap mendarat di sana — beranda perannya, ROLE_HOME_REGISTRY).
  // Sesi #087 — meja MD & Admin Gudang (peran barunya lewat ROLE_NAV, pola yang sama).
  {
    type: "standalone",
    id:    "md-desk",
    label: "Meja MD",
    icon:  Palette,
    roles: [],
    view:  "md-desk",
  },
  {
    type: "standalone",
    id:    "warehouse-admin-desk",
    label: "Meja Gudang",
    icon:  Warehouse,
    roles: [],
    view:  "warehouse-admin-desk",
  },
  // REVISI SAMPEL — Meja Admin Sample (peran `sample_admin` lewat ROLE_NAV).
  {
    type: "standalone",
    id:    "sample-admin-desk",
    label: "Meja Sample",
    icon:  Scissors,
    roles: [],
    view:  "sample-admin-desk",
  },
  // IA 2026-10 (D5) — admin dulu melihat 5 meja peran sebagai menu lepas di "Kerja Saya".
  // Kini satu grup untuk admin; peran pemiliknya tetap melihat mejanya sendiri lewat ROLE_NAV
  // (entri standalone di atas, roles kosong = hanya lewat overlay).
  {
    type:    "group",
    groupId: "meja-peran",
    label:   "Meja Peran",
    icon:    ClipboardList,
    roles:   ["admin"],
    items: [
      { id: "sales-admin-desk",     label: "Meja Admin Sales", icon: ClipboardList, roles: ["admin"], view: "sales-admin-desk" },
      { id: "md-desk",              label: "Meja MD",          icon: Palette,       roles: ["admin"], view: "md-desk" },
      { id: "warehouse-admin-desk", label: "Meja Gudang",      icon: Warehouse,     roles: ["admin"], view: "warehouse-admin-desk" },
      { id: "sample-admin-desk",    label: "Meja Sample",      icon: Scissors,      roles: ["admin"], view: "sample-admin-desk" },
    ],
  },

  // ── PENJUALAN ────────────────────────────────────────────────────────────────
  {
    type:    "group",
    groupId: "penjualan",
    label:   "Penjualan",
    icon:    ShoppingCart,
    roles:   ["admin", "sales", "manager"],
    items: [
      { id: "sales",            label: "POS", icon: ShoppingBag, roles: ["admin", "sales"] },
      // SPECIAL ORDER — permintaan produk custom pelanggan (referensi/pattern/warna/handfeel) → routing ke Desainer & R&D.
      { id: "special-orders",   label: "Pesanan Khusus", icon: Sparkles, roles: ["admin", "sales", "manager", "sales_admin"], view: "special-orders" },
      { id: "sales-orders",     label: "Pesanan",    icon: FileText,    roles: ["admin", "sales", "manager"], hub: "sales-orders" },
      // REVISI SAMPEL — daftar pesanan sample TERPISAH dari SO biasa (klien: "jangan digabung").
      { id: "sample-orders",    label: "Pesanan Sample", icon: Scissors, roles: ["admin", "sales", "manager"], view: "sample-orders" },
      { id: "customers-crm",    label: "Pelanggan",    icon: Users,       roles: ["admin", "sales", "manager"], hub: "customers-crm" },
      // Sales hanya melihat tab "Harga per Pelanggan" di hub ini (tab lain admin/manager).
      { id: "products-pricing", label: "Produk & Harga",     icon: Layers3,     roles: ["admin", "manager", "sales"], hub: "products-pricing" },
    ],
  },

  // ── RETUR (L08 LN-080) — SATU menu untuk semua arah retur: pelanggan, antar-PT, supplier,
  // plus kebijakannya. Alur & keputusan tiap arah tetap terpisah (layar yang sama seperti dulu).
  {
    type:  "standalone",
    id:    "returns-hub",
    label: "Retur",
    icon:  RotateCcw,
    // qc: F-11-layar · md & md_quality (UAT 23 Okt): cutloss retur — catat qty cacat, pecah roll, SJ potongan baik
    roles: ["admin", "manager", "sales", "sales_admin", "warehouse", "finance", "qc", "md", "md_quality"],
    hub:   "returns-hub",
  },

  // ── KUALITAS (23 Okt, IA) — QC & inspeksi = modul sendiri, bukan bagian operasi gudang: gudang menyimpan &
  // memindah barang, kualitas memutus mutu (grade, cacat, tahan/lepas). Peran QC/MD Quality/MD masuk lewat ROLE_NAV.
  {
    type:  "standalone",
    id:    "quality-hub",
    label: "Kualitas",
    icon:  ShieldCheck,
    roles: ["admin", "manager", "warehouse", "warehouse_admin"],
    hub:   "quality-hub",
  },

  // ── PEMBELIAN ────────────────────────────────────────────────────────────────
  {
    type:    "group",
    groupId: "pembelian",
    label:   "Pembelian",
    icon:    ClipboardList,
    roles:   ["admin", "manager", "warehouse", "finance"],
    items: [
      { id: "sourcing",         label: "Pengadaan",    icon: Target,        roles: ["admin", "manager", "warehouse"], hub: "sourcing" },
      // Cek UI UAT v3 (2026-10-22) — Gudang punya izin makloon_order.issue/receive & tab "Order Makloon"/"Klaim Selisih
      // Makloon" untuk peran gudang, tetapi induknya tertutup → tab tidak pernah tampil (pengeluaran bahan makloon buntu).
      { id: "purchase-orders",  label: "Pesanan Pembelian",  icon: ClipboardList, roles: ["admin", "manager", "finance", "warehouse"],   hub: "purchase-orders" },
      // MN-T1 — "Hutang Pemasok" pindah ke Keuangan › Hutang (id menu tetap `accounts-payable`).
      { id: "master-pembelian", label: "Master Pembelian",        icon: Factory,       roles: ["admin", "manager"],              hub: "master-pembelian" },
      { id: "cs-bom",           label: "Bahan Cetak",            icon: Printer,       roles: ["admin"], comingSoon: true },
    ],
  },

  // ── R&D (FASE F) — hulu rantai: spesifikasi → labdip/proofing → kontrak harga.
  // Menu ini SENGAJA hanya berisi PROSES R&D. Urusan ORANG & KARYA desain dipisah
  // ke menu "Desainer" di bawah (keputusan pemilik PS-18: jangan digabung).
  {
    type:  "standalone",
    id:    "rnd-hub",
    label: "R&D",
    icon:  FlaskConical,
    roles: ["admin", "manager", "sales", "warehouse"],
    hub:   "rnd-hub",
  },

  // ── DESAINER (PS-18) — menu TERPISAH dari R&D: KPI desainer, master desain
  // & galeri artwork. Sebelumnya tersebar di hub R&D dan hub SDM sehingga
  // pemilik harus berpindah dua menu untuk menilai satu orang.
  {
    type:  "standalone",
    id:    "designer-hub",
    label: "Desainer",
    icon:  Palette,
    // FASE D — peran `designer` (ke-7) masuk di sini: hub ini memuat papan
    // Permintaan Desain (pintu kerjanya) + Galeri Desain (tempat karyanya).
    roles: ["admin", "manager", "designer"],
    hub:   "designer-hub",
  },

  // ── MARKETING ─────────────────────────────────────────────────────────────────
  {
    type:  "standalone",
    id:    "marketing-hub",
    label: "Marketing & Sosmed",
    icon:  Megaphone,
    roles: ["admin", "manager", "designer", "sales", "sales_admin"],
    hub:   "marketing-hub",
  },

  // ── GUDANG ───────────────────────────────────────────────────────────────────
  {
    type:    "group",
    groupId: "gudang",
    label:   "Gudang & Logistik",
    icon:    Warehouse,
    roles:   ["admin", "warehouse", "manager", "sales", "driver", "sales_admin", "warehouse_admin", "md", "finance"],
    items: [
      // FASE E-8 (E8.3 · SD3) — `sales` DICABUT dari menu ini. Bukan pengetatan
      // baru: `/api/wms/tasks` memang sudah 403 untuk sales, jadi menunya adalah
      // LAYAR MATI — pengguna mengeklik, layar menolak, dan ia menyalahkan dirinya
      // sendiri. Gantinya sales mendapat "Perjalanan Pesanan" (E8.14) yang memuat
      // progres gudang TANPA membuka layar gudang. `sales_admin` tetap melihatnya
      // (izin `wms.view` — memantau, tanpa aksi) lewat overlay ROLE_NAV.
      // 2026-09-29 — "Kedatangan Barang" (SJ + OCR) DIKONSOLIDASI ke hub Operasi Gudang (tab Barang Masuk);
      // dulu menu terpisah yang fungsinya sama dengan tab Barang Masuk. Finance hanya melihat tab itu.
      { id: "wms-operations",     label: "Operasi Gudang", icon: Warehouse, roles: ["admin", "warehouse", "manager", "warehouse_admin", "finance"], hub: "wms-operations" },
      { id: "stock-atp",          label: "Stok & ATP",           icon: Boxes,     roles: ["admin", "warehouse", "manager", "sales"], hub: "stock-atp" },
      // Fase 3 · P8 (D-25) — "Produksi" diperjelas: BOM produksi in-house (resep makloon ada di Master Pembelian).
      { id: "production",         label: "BOM Produksi In-House",  icon: Factory,   roles: ["admin", "manager", "warehouse"] },
      { id: "wms-locations",      label: "Lokasi Rak",     icon: MapPin,    roles: ["admin", "warehouse", "manager"] },
      { id: "md-warehouses",      label: "Data Gudang",      icon: Warehouse, roles: ["admin", "warehouse", "manager"] },
      // Pengiriman (ekspedisi / armada sendiri, foto muat & POD). Sopir hanya melihat item ini.
      { id: "logistics",          label: "Pengiriman", icon: Truck, roles: ["admin", "manager", "warehouse", "driver", "sales", "sales_admin", "warehouse_admin"], view: "logistics" },
      // MN-T1 — dari Kas & Aset (grup dihapus): catatan operasional armada = pekerjaan gudang & logistik (view sama).
      { id: "vehicle-logs",       label: "Kendaraan",  icon: Car,   roles: ["admin", "manager", "warehouse", "sales"], view: "vehicle-logs" },
      // IA 2026-10 (D1) — RFID adalah teknologi gudang, bukan domain: 4 menu jadi satu hub di sini.
      { id: "rfid-hub",           label: "RFID",       icon: Cpu,   roles: ["admin", "warehouse", "manager"], hub: "rfid-hub" },   // FIX-1 K-B1-07
      // IA 2026-10 (C8) — eskalasi tugas inbound/outbound = pekerjaan gudang.
      { id: "escalations",        label: "Eskalasi Gudang", icon: AlertTriangle, roles: ["admin", "warehouse", "manager"], view: "escalations" },
    ],
  },

  // ── KEUANGAN — MN-T1 (K-46, rencana 01 §2): uang harian, 5 entri. Satu pekerjaan = satu entri, langkahnya tab
  // (hubTabs.js). Dulu 18 entri dalam 4 grup (Keuangan · Akuntansi & Pajak · Kas & Aset · Hutang Pemasok di Pembelian) +
  // sub-tab keuangan di CRM & Pengaturan; id lama tetap hidup (alias `viewAliases.js` + rute cadangan). Grup tampil
  // bila ada minimal satu entri yang boleh (Sales: Piutang & Kas Kecil; Gudang: Kontrabon & Antar-PT).
  {
    type:    "group",
    groupId: "keuangan",
    label:   "Keuangan",
    icon:    DollarSign,
    roles:   ["admin", "manager", "sales", "warehouse"],
    items: [
      { id: "finance-tower", label: "Beranda Keuangan", icon: PieChart,     roles: ["admin", "manager"], hub: "finance-tower" },
      { id: "ar-aging",      label: "Piutang",          icon: TrendingDown, roles: ["admin", "manager", "sales"], hub: "ar-aging" },
      { id: "accounts-payable", label: "Hutang",        icon: Receipt,      roles: ["admin", "manager", "warehouse"], hub: "accounts-payable" },
      { id: "cash-bank",     label: "Kas & Bank",       icon: CreditCard,   roles: ["admin", "manager", "sales"], hub: "cash-bank" },
      // IA 2026-10 (D2) — saldo/settlement/pinjaman antar-PT. MN-T1 — dari Akuntansi & Pajak ke Keuangan (view sama).
      { id: "interco-transactions", label: "Antar-PT",  icon: Briefcase,    roles: ["admin", "manager", "warehouse", "finance"], view: "interco-transactions" },
    ],
  },

  // ── AKUNTANSI & PAJAK — MN-T1: pembukuan, 5 entri, urut alur tutup buku. Gudang dicabut (Antar-PT pindah ke Keuangan).
  {
    type:    "group",
    groupId: "akuntansi",
    label:   "Akuntansi & Pajak",
    icon:    FileStack,
    roles:   ["admin", "manager"],
    items: [
      { id: "ledger",      label: "Buku Besar",  icon: FileStack,    roles: ["admin", "manager"], hub: "ledger" },
      // MN-T1 — Tutup Buku · Buka Periode · Posting Gagal: tiga entri menjadi satu hub (id menu tetap `closing`).
      { id: "closing",     label: "Tutup Buku",  icon: CalendarX,    roles: ["admin", "manager"], hub: "closing" },
      { id: "fin-reports", label: "Laporan",     icon: FileBarChart, roles: ["admin", "manager"], hub: "fin-reports" },
      { id: "tax-hub",     label: "Pajak",       icon: Percent,      roles: ["admin", "manager"], hub: "tax-hub" },
      // MN-T1 — dari Kas & Aset (grup dihapus; id grup `kas-aset` = alias legacy ke Kas & Bank › Kas Kecil).
      { id: "fixed-assets", label: "Aset Tetap", icon: Boxes,        roles: ["admin", "manager"], view: "fixed-assets" },
    ],
  },

  // ── SDM (HRD) ────────────────────────────────────────────────────────────────
  {
    type:    "group",
    groupId: "hrd",
    label:   "SDM",
    icon:    Users,
    // MN-T1 — + sales: SDM › Kinerja & Insentif › Kinerja Sales (dulu sub-tab CRM) sampai KM-T5 menggantinya.
    roles:   ["admin", "manager", "sales", "finance"],   // KM-T1 — + finance: Kinerja & Insentif › Target & Aturan (lihat)
    items: [
      { id: "hr-people",         label: "Karyawan", icon: UserCheck,  roles: ["admin", "manager"], hub: "hr-people" },
      { id: "hr-attendance-hub", label: "Kehadiran",      icon: Clock,      roles: ["admin", "manager"], hub: "hr-attendance-hub" },
      // PY-T4 — + finance: Penggajian › Setoran & Pajak (bayar gaji & setor BPJS/PPh 21; izin `payroll.pay`).
      { id: "hr-payroll-hub",    label: "Penggajian",               icon: Calculator, roles: ["admin", "manager", "finance"], hub: "hr-payroll-hub" },
      // MN-T1 — "KPI" → "Kinerja & Insentif": menyerap Kinerja Sales & Skema (CRM) + Komisi & Insentif (Pengaturan).
      { id: "hr-kpi-hub",        label: "Kinerja & Insentif", icon: Target, roles: ["admin", "manager", "sales", "finance"], hub: "hr-kpi-hub" },
    ],
  },

  // ── ANALITIK (satu hub) ──────────────────────────────────────────────────────
  {
    type:  "standalone",
    id:    "analytics",
    label: "Analitik",
    icon:  BarChart3,
    roles: ["admin", "manager", "warehouse_admin"],
    hub:   "analytics",
  },
  // L11 LN-110 — Pusat Export: isi tiap dataset tetap dijaga izin modul sumbernya.
  {
    type:  "standalone",
    id:    "export-center",
    label: "Pusat Export",
    icon:  FileSpreadsheet,
    // FIX-4 (K-B4-07) — petugas gudang: unduhan besar dari tombol daftar diambil di Pusat Export → Pekerjaan;
    // dataset yang terbuka untuknya dibatasi daftar putih gudang di server.
    roles: ["admin", "manager", "sales_admin", "finance", "sales", "md", "warehouse_admin", "designer", "warehouse"],
    view:  "export-center",
  },

  // ── UTILITAS & PENGATURAN ────────────────────────────────────────────────────
  {
    type:  "standalone",
    id:    "document-center",
    label: "Pusat Dokumen",
    icon:  FileStack,
    roles: ["admin", "sales", "manager", "warehouse"],
    // FASE G-4 — hub: tab "Daftar Dokumen" + "Jejak Dokumen" (lihat HUB_TABS).
    hub:   "document-center",
    view:  "document-center",
  },
  // ── PENGATURAN — KP-T9 (K-46): SEMBILAN hub tanpa sub-judul, urut cara mengisi PT baru (PT → orang → persetujuan →
  // aturan per bagian → dokumen → sistem). Dulu (fase 3 · P2, P16-K1) 12 hub + 2 sub-judul, tiga di antaranya ber-tab
  // tunggal. groupId TETAP `settings-hub` (ROLE_NAV sales_admin & katalog modul tetap sah); alamat lama
  // `?view=settings-hub` = alias legacy, empat id hub yang hilang (`settings-purchasing`, `settings-rnd`,
  // `settings-masters`, `settings-notify`) = alias legacy ke tab barunya (viewAliases.js). Editor lama mempertahankan
  // view id-nya — hanya pindah hub. warehouse_admin: Gudang, Pembelian & Produksi (Penerimaan Barang, Grade Mutu);
  // sales_admin (ROLE_NAV): Penjualan › Kebijakan Retur + Gudang, Pembelian & Produksi › Grade Mutu.
  {
    type:    "group",
    groupId: "settings-hub",
    label:   "Pengaturan",
    icon:    Settings,
    roles:   ["admin", "manager", "warehouse_admin"],
    items: [
      { id: "settings-company",    label: "Perusahaan (PT)",              icon: Building2,    roles: ["admin", "manager"], hub: "settings-company" },
      { id: "settings-access",     label: "Pengguna & Hak Akses",         icon: UserCog,      roles: ["admin", "manager"], hub: "settings-access" },
      { id: "settings-approval",   label: "Persetujuan",                  icon: ShieldCheck,  roles: ["admin", "manager"], hub: "settings-approval" },
      { id: "settings-sales",      label: "Penjualan",                    icon: ShoppingCart, roles: ["admin", "manager"], hub: "settings-sales" },
      { id: "settings-warehouse",  label: "Gudang, Pembelian & Produksi", icon: Warehouse,    roles: ["admin", "manager", "warehouse_admin"], hub: "settings-warehouse" },
      { id: "settings-finance",    label: "Keuangan & Pajak",             icon: Landmark,     roles: ["admin", "manager"], hub: "settings-finance" },
      { id: "settings-hr",         label: "SDM",                          icon: Users,        roles: ["admin", "manager"], hub: "settings-hr" },
      { id: "settings-documents",  label: "Dokumen & Notifikasi",         icon: Printer,      roles: ["admin", "manager"], hub: "settings-documents" },
      { id: "settings-system",     label: "Sistem",                       icon: Cpu,          roles: ["admin", "manager"], hub: "settings-system" },
    ],
  },
  {
    type:  "standalone",
    id:    "hr-my-profile",
    label: "Profil Saya",
    icon:  IdCard,
    roles: ["admin", "sales", "manager", "warehouse"],
    view:  "hr-my-profile",
  },
];

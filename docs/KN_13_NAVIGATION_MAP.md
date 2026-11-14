# KN_13 — NAVIGATION MAP
## Kain Nusantara Platform — Master Navigation Structure

**Versi:** 1.0 | **Berlaku sejak:** 2026-05-23

---

## 📍 PURPOSE

Navigation Map adalah **Single Source of Truth (SSOT)** untuk struktur menu & routing aplikasi.

**Wajib digunakan untuk:**
1. **Sebelum tambah menu/halaman baru** — Check apakah sudah ada, tentukan posisi yang tepat
2. **Onboarding baru** — Pahami struktur app secara keseluruhan
3. **Refactoring** — Pastikan tidak ada menu redundant
4. **Testing** — Test suite harus cover semua nodes di navigation map

**RULE:** Setiap halaman/fitur baru **WAJIB** di-mapping di sini **SEBELUM** coding.

---

## 🏛️ NAVIGATION HIERARCHY

```
KAIN NUSANTARA APP
│
├── 🏠 HOME / DASHBOARD (Role-Specific Landing)
│   ├── Admin: Admin Dashboard (Master Data Overview)
│   ├── Sales: Sales Portal (POS)
│   ├── Manager: Executive Dashboard (Analytics)
│   └── Warehouse: Operations View (WMS)
│
├── 💼 SALES & POS
│   ├── POS (Sales Portal)
│   │   ├── Product Catalog (Visual Grid)
│   │   ├── Cart Panel (Right Sidebar)
│   │   └── Customer Panel (Dropdown)
│   │
│   └── Orders (Order Management)
│       ├── Dashboard & Analytics Tab
│       │   ├── KPI Cards (Revenue, Top Customers, Status)
│       │   └── Charts (Status Distribution, Trend)
│       │
│       └── Order List Tab
│           ├── Filter by Status (Pills)
│           ├── Search (Order/Customer/Product)
│           ├── Order Cards (List View)
│           └── Order Detail Panel (Right Sidebar)
│               ├── Status Timeline
│               ├── Item List
│               ├── Allocation (per Warehouse)
│               └── Actions (Approve, Confirm, Cancel, Release)
│
├── 🏭 WAREHOUSE & OPERATIONS (WMS)
│   ├── Stok & Inventori
│   │   ├── Tab: Stok
│   │   │   ├── KPI Cards (Total On Hand, Available, Reserved, Low Stock)
│   │   │   ├── Warehouse Filter Pills
│   │   │   ├── Search (SKU/Name/Warehouse)
│   │   │   ├── Inventory Table
│   │   │   └── Reserved Details Panel (Right Sidebar)
│   │   │
│   │   └── Tab: Ledger (Movement History)
│   │       ├── Movement Type Filter
│   │       ├── Date Range Picker
│   │       └── Movement List (Chronological)
│   │
│   ├── Inbound / Penerimaan
│   │   ├── Task List (Left Panel)
│   │   │   ├── Status Filter Pills (Waiting/Receiving/QC/Escalated)
│   │   │   ├── Task Cards
│   │   │   └── Task Actions (Start, Complete, Escalate)
│   │   │
│   │   └── Scan Panel (Right Panel)
│   │       ├── Active Task Info
│   │       ├── Barcode/QR Scanner (Camera/Input)
│   │       ├── Scanned Items List
│   │       └── Complete Button
│   │
│   ├── Outbound / Pengiriman
│   │   ├── Task List (Left Panel)
│   │   │   ├── Status Filter Pills (Created/Picking/Packing/Staging/Dispatched)
│   │   │   ├── Task Cards
│   │   │   └── Task Actions (Pick, Pack, Dispatch)
│   │   │
│   │   └── Scan Panel (Right Panel)
│   │       ├── Active Task Info
│   │       ├── Barcode/QR Scanner
│   │       ├── Picked Items List
│   │       └── Dispatch Button
│   │
│   ├── Transfer Antar Gudang
│   │   ├── Transfer List
│   │   │   ├── Status Filter (Draft/Waiting/Approved/In Transit/Received)
│   │   │   ├── Transfer Cards
│   │   │   └── Actions (Approve, Reject, Dispatch, Receive)
│   │   │
│   │   └── Create Transfer Form (Modal)
│   │       ├── Source Warehouse
│   │       ├── Destination Warehouse
│   │       ├── Item Selection (Multi)
│   │       └── Notes
│   │
│   └── Cycle Count
│       ├── Count Session List
│       │   ├── Status Filter (Draft/In Progress/Submitted/Approved)
│       │   ├── Session Cards
│       │   └── Actions (Start, Submit, Approve, Reject)
│       │
│       └── Count Entry Form
│           ├── Product Selection
│           ├── Warehouse Selection
│           ├── Expected Qty (from system)
│           ├── Actual Qty (counted)
│           └── Variance Indicator
│
├── 📊 PURCHASING
│   ├── Purchase Order List
│   │   ├── Status Filter (Pending/Receiving/Completed/Partial/Cancelled)
│   │   ├── PO Cards
│   │   └── PO Detail Panel (Right Sidebar)
│   │       ├── Supplier Info
│   │       ├── Item List
│   │       ├── Expected Delivery Date
│   │       └── Actions (Receive, Cancel)
│   │
│   └── Create PO Form (Modal)
│       ├── Supplier Name
│       ├── Warehouse Selection
│       ├── Item Selection (Multi)
│       ├── Quantity & Price per Item
│       └── Notes
│
├── 📝 DOCUMENTS & PRINT
│   ├── Print Center
│   │   ├── Surat Jalan Generator
│   │   │   ├── Select Order
│   │   │   ├── Template Selection
│   │   │   ├── Preview
│   │   │   └── Print Button
│   │   │
│   │   ├── Invoice Generator
│   │   │   ├── Select Order
│   │   │   ├── Template Selection
│   │   │   ├── Preview
│   │   │   └── Print Button
│   │   │
│   │   └── Label Printer
│   │       ├── Product Selection (Dropdown)
│   │       ├── Quantity Input
│   │       ├── Label Size (80x50mm, A4)
│   │       ├── Preview (Barcode + SKU + Name)
│   │       └── Generate Button
│   │
│   └── Template Management (Admin Only)
│       ├── Template List (Surat Jalan, Invoice)
│       ├── Template Editor
│       │   ├── Header/Footer Text
│       │   ├── Column Selection
│       │   ├── Logo URL
│       │   ├── Paper Size & Orientation
│       │   └── Signature Fields
│       │
│       └── Actions (Create, Edit, Delete, Set Default)
│
├── 📊 REPORTS & ANALYTICS
│   ├── Executive Dashboard (Manager/Admin)
│   │   ├── KPI Overview (Revenue, Orders, Stock Value, Fulfillment Rate)
│   │   ├── Charts (Revenue Trend, Top Products, Warehouse Performance)
│   │   ├── Timeframe Selector (7/30/90 days)
│   │   └── Export Button (planned)
│   │
│   └── Report Library
│       ├── Stock Aging Report
│       ├── Reservation Funnel Report
│       ├── Order Velocity Report
│       ├── Top Customers Report
│       ├── Warehouse Utilization Report
│       └── Summary Report
│
├── ⚙️ ADMIN & MASTER DATA
│   ├── Master Data Management
│   │   ├── Products
│   │   │   ├── Product List (Table)
│   │   │   ├── Search & Filter (Category, Status)
│   │   │   ├── Product Form (Toggle Expand)
│   │   │   │   ├── SKU, Name, Category, Variant
│   │   │   │   ├── Color, Motif, Grade
│   │   │   │   ├── Supplier, Base Unit, Price
│   │   │   │   ├── Image URL
│   │   │   │   └── UOM Conversions (optional)
│   │   │   │
│   │   │   └── Actions (Create, Edit, Soft Delete, Import CSV, Export CSV)
│   │   │
│   │   ├── Customers
│   │   │   ├── Customer List (Table)
│   │   │   ├── Search & Filter (Type, City)
│   │   │   ├── Customer Form (Toggle Expand)
│   │   │   │   ├── Name, PIC, Phone, Email
│   │   │   │   ├── Type (Retailer/Wholesaler/Boutique)
│   │   │   │   ├── City, Address
│   │   │   │   └── Addresses (Multi, with Primary)
│   │   │   │
│   │   │   └── Actions (Create, Edit, Soft Delete, Import CSV, Export CSV)
│   │   │
│   │   ├── Warehouses
│   │   │   ├── Warehouse List (Table)
│   │   │   ├── Search & Filter (City, Active)
│   │   │   ├── Warehouse Form (Toggle Expand)
│   │   │   │   ├── Code, Name, City
│   │   │   │   ├── Lat/Lng (Coordinates)
│   │   │   │   ├── Zone > Rack > Bin Hierarchy
│   │   │   │   └── Active Status
│   │   │   │
│   │   │   └── Actions (Create, Edit, Soft Delete, Import CSV, Export CSV)
│   │   │
│   │   ├── UOMs (Unit of Measure)
│   │   │   ├── UOM List (Table)
│   │   │   ├── UOM Form (Toggle Expand)
│   │   │   │   ├── Code, Name
│   │   │   │   ├── Base Type (length/volume/weight/count)
│   │   │   │   └── Precision (decimal places)
│   │   │   │
│   │   │   └── Actions (Create, Edit, Delete)
│   │   │
│   │   └── Users
│   │       ├── User List (Table)
│   │       ├── Search & Filter (Role, Status)
│   │       ├── User Form (Toggle Expand)
│   │       │   ├── Name, Email
│   │       │   ├── Role (admin/sales/manager/warehouse)
│   │       │   ├── Password (for new users)
│   │       │   └── Status (active/inactive)
│   │       │
│   │       └── Actions (Create, Edit, Deactivate)
│   │
│   ├── Permission Settings
│   │   ├── Permission Matrix (Role x Module)
│   │   │   ├── Rows: Roles (admin, sales, manager, warehouse)
│   │   │   ├── Columns: Modules (products, customers, orders, wms, etc)
│   │   │   ├── Cells: Actions (read, write, delete, approve, etc)
│   │   │   └── Checkboxes untuk toggle permissions
│   │   │
│   │   └── Actions (Update Matrix, Reset to Default)
│   │
│   ├── Audit Logs
│   │   ├── Audit List (Table, Chronological)
│   │   ├── Filter (Date Range, Actor, Action, Entity Type)
│   │   ├── Search (by Entity ID, Reason)
│   │   └── Log Entry Details
│   │       ├── Actor (User) + Role
│   │       ├── Action (create, update, delete, approve, etc)
│   │       ├── Entity Type + Entity ID
│   │       ├── Before/After Data (JSON diff)
│   │       └── Timestamp + Reason
│   │
│   └── System Settings (Planned)
│       ├── Tax Configuration (PPN %)
│       ├── Reservation Expiry Duration
│       ├── Email/SMTP Settings
│       └── Notification Preferences
│
├── 🔔 ESCALATIONS (Global)
│   ├── Escalation List
│   │   ├── Filter by Status (Pending/In Review/Resolved)
│   │   ├── Filter by Type (Inbound/Outbound/Transfer/Cycle Count)
│   │   ├── Escalation Cards
│   │   └── Escalation Detail Panel
│   │       ├── Source Task Link
│   │       ├── Issue Description (Reason)
│   │       ├── Escalated By + Timestamp
│   │       ├── Resolution Notes (by Manager)
│   │       └── Actions (Review, Resolve, Re-assign)
│   │
│   └── Escalation Form (Modal, from WMS tasks)
│       ├── Task ID (auto)
│       ├── Reason (required, textarea)
│       └── Submit Button
│
├── ❓ HELP & TOURS
│   ├── Guided Tour Menu (Modal)
│   │   ├── Role Badge (current user role)
│   │   ├── Tour List (filtered by role)
│   │   │   ├── Tour: Create Sales Order (5 steps)
│   │   │   ├── Tour: Approve Order (5 steps)
│   │   │   ├── Tour: Process Inbound (4 steps)
│   │   │   ├── Tour: Process Outbound (4 steps)
│   │   │   ├── Tour: Order Dashboard (5 steps)
│   │   │   ├── Tour: Inventory Management (6 steps)
│   │   │   └── Tour: Admin Master Data (7 steps)
│   │   │
│   │   └── Start Tour Button (per tour)
│   │
│   └── Tour Overlay (Active Tour)
│       ├── Highlight Target (Pulse Ring)
│       ├── Tooltip (Title + Instructions)
│       ├── Step Counter (e.g., "2/5")
│       └── Navigation (Previous, Next, Exit)
│
└── 👤 USER MENU (Top Right)
    ├── User Info (Name + Role Badge)
    ├── Profile Settings (Planned)
    ├── Change Password (Planned)
    └── Logout
```

---

## 📋 ROLE-BASED ACCESS MATRIX

| Section | Admin | Sales | Manager | Warehouse |
|---|:---:|:---:|:---:|:---:|
| **Home / Dashboard** | ✅ (Admin) | ✅ (POS) | ✅ (Analytics) | ✅ (WMS) |
| **Sales & POS** | ✅ Full | ✅ Full | 👁️ Read | ❌ No |
| **Orders** | ✅ Full | ✅ Create/View | ✅ Approve/View | 👁️ Read |
| **WMS (Stok)** | ✅ Full | 👁️ Read | 👁️ Read | ✅ Full |
| **WMS (Inbound)** | ✅ Full | ❌ No | 👁️ Read | ✅ Full |
| **WMS (Outbound)** | ✅ Full | ❌ No | 👁️ Read | ✅ Full |
| **WMS (Transfer)** | ✅ Full | ❌ No | ✅ Approve | ✅ Create/Execute |
| **WMS (Cycle Count)** | ✅ Full | ❌ No | ✅ Approve | ✅ Create/Count |
| **Purchasing** | ✅ Full | ❌ No | ✅ Approve | 👁️ Read |
| **Documents & Print** | ✅ Full | ✅ Generate | ✅ Generate | ✅ Generate |
| **Reports & Analytics** | ✅ Full | 👁️ Read | ✅ Full | 👁️ Limited |
| **Admin & Master Data** | ✅ Full | ❌ No | 👁️ Read | ❌ No |
| **Permission Settings** | ✅ Full | ❌ No | ❌ No | ❌ No |
| **Audit Logs** | ✅ Full | ❌ No | 👁️ Read | ❌ No |
| **Escalations** | ✅ Full | ❌ No | ✅ Review | ✅ Create |
| **Help & Tours** | ✅ All Tours | ✅ Sales Tours | ✅ Manager Tours | ✅ WMS Tours |

---

## 📏 NAVIGATION IMPLEMENTATION (Frontend)

### Sidebar Structure (App.js)

```jsx
const navigationConfig = {
  admin: [
    { id: 'home', label: 'Admin Dashboard', icon: LayoutDashboard, view: 'admin' },
    { id: 'pos', label: 'POS', icon: ShoppingCart, view: 'pos' },
    { id: 'orders', label: 'Orders', icon: ShoppingBag, view: 'orders' },
    { id: 'wms', label: 'Warehouse & Operations', icon: Warehouse, view: 'wms' },
    { id: 'purchasing', label: 'Purchasing', icon: ShoppingBasket, view: 'purchasing' },
    { id: 'documents', label: 'Documents & Print', icon: FileText, view: 'documents' },
    { id: 'reports', label: 'Reports & Analytics', icon: BarChart3, view: 'reports' },
    { id: 'admin', label: 'Admin & Master Data', icon: Settings, view: 'admin' },
    { id: 'escalations', label: 'Escalations', icon: AlertTriangle, view: 'escalations' },
  ],
  sales: [
    { id: 'home', label: 'POS', icon: ShoppingCart, view: 'pos' },
    { id: 'orders', label: 'Orders', icon: ShoppingBag, view: 'orders' },
    { id: 'documents', label: 'Documents & Print', icon: FileText, view: 'documents' },
  ],
  manager: [
    { id: 'home', label: 'Executive Dashboard', icon: BarChart3, view: 'reports' },
    { id: 'orders', label: 'Orders', icon: ShoppingBag, view: 'orders' },
    { id: 'wms', label: 'Warehouse & Operations', icon: Warehouse, view: 'wms' },
    { id: 'purchasing', label: 'Purchasing', icon: ShoppingBasket, view: 'purchasing' },
    { id: 'reports', label: 'Reports & Analytics', icon: BarChart3, view: 'reports' },
    { id: 'escalations', label: 'Escalations', icon: AlertTriangle, view: 'escalations' },
  ],
  warehouse: [
    { id: 'home', label: 'Warehouse & Operations', icon: Warehouse, view: 'wms' },
    { id: 'documents', label: 'Documents & Print', icon: FileText, view: 'documents' },
    { id: 'escalations', label: 'Escalations', icon: AlertTriangle, view: 'escalations' },
  ],
};
```

### WMS Tabs (OperationsView)

```jsx
const wmsTabs = [
  { id: 'stok', label: 'Stok & Inventori', icon: Package },
  { id: 'inbound', label: 'Inbound / Penerimaan', icon: PackagePlus },
  { id: 'outbound', label: 'Outbound / Pengiriman', icon: PackageMinus },
  { id: 'transfer', label: 'Transfer Antar Gudang', icon: ArrowLeftRight },
  { id: 'cycle', label: 'Cycle Count', icon: ClipboardCheck },
];
```

### Orders Tabs (OrdersView)

```jsx
const ordersTabs = [
  { id: 'dashboard', label: 'Dashboard & Analytics', icon: BarChart3 },
  { id: 'list', label: 'Order List', icon: List },
];
```

---

## 🧪 TEST DATA-TESTID MAPPING

**WAJIB:** Setiap interactive element dan info-display element harus punya `data-testid`.

### Sidebar
```jsx
<button data-testid="nav-pos">POS</button>
<button data-testid="nav-orders">Orders</button>
<button data-testid="nav-wms">Warehouse & Operations</button>
<button data-testid="nav-purchasing">Purchasing</button>
<button data-testid="nav-documents">Documents & Print</button>
<button data-testid="nav-reports">Reports & Analytics</button>
<button data-testid="nav-admin">Admin & Master Data</button>
<button data-testid="nav-escalations">Escalations</button>
<button data-testid="help-tours-button">Help & Tours</button>
```

### WMS Tabs
```jsx
<button data-testid="wms-tab-stok">Stok</button>
<button data-testid="wms-tab-inbound">Inbound</button>
<button data-testid="wms-tab-outbound">Outbound</button>
<button data-testid="wms-tab-transfer">Transfer</button>
<button data-testid="wms-tab-cycle">Cycle Count</button>
```

### Orders Dashboard
```jsx
<div data-testid="dashboard-metric-revenue">...</div>
<div data-testid="dashboard-top-customers">...</div>
<div data-testid="dashboard-status-distribution">...</div>
```

### Inventory Filters
```jsx
<div data-testid="inventory-warehouse-filters">...</div>
<input data-testid="inventory-search" />
```

---

## 🔍 NAVIGATION FIRST POLICY

**BEFORE adding any new page/feature:**

1. **Check if exists:**
   ```bash
   grep -r "feature_name" /app/docs/KN_13_NAVIGATION_MAP.md
   ```

2. **If NOT exists, decide placement:**
   - Which parent section? (Sales, WMS, Admin, etc)
   - Which role can access?
   - What's the route?
   - What's the data-testid?

3. **Update this file FIRST** before coding:
   - Add to hierarchy tree
   - Add to role access matrix
   - Add to implementation code snippet
   - Add to test data-testid mapping

4. **Then code:**
   - Backend: Create router
   - Frontend: Create component
   - Add to sidebar/tab config
   - Add data-testid attributes

---

## ⚠️ ANTI-PATTERNS (JANGAN LAKUKAN)

### ❌ 1. Menu Redundan
```
❌ BAD:
  ├── Sales Orders (di Sales section)
  ├── Order Management (di Operations section)
  └── View Orders (di Reports section)

✅ GOOD:
  └── Orders (satu tempat, dengan tabs Dashboard vs List)
```

### ❌ 2. Deep Nesting (>4 levels)
```
❌ BAD:
  Sales > Orders > Details > Items > Edit Item Modal > Warehouse Selection
  (6 levels!)

✅ GOOD:
  Sales > Orders > [Detail Panel] > Edit Item Modal
  (3 levels, panel bukan nested route)
```

### ❌ 3. Role-Specific Duplicate Pages
```
❌ BAD:
  /admin/dashboard (admin only)
  /manager/dashboard (manager only)
  /sales/dashboard (sales only)

✅ GOOD:
  /dashboard (conditional content based on role)
```

---

## 🚦 NAVIGATION CHANGE PROTOCOL

### For Minor Changes (adding data-testid, renaming label)
- Update this file
- Update code
- No review needed

### For Major Changes (new section, restructure)
1. **Propose change** di SESSION_LOG.md
2. **Update KN_13** dengan [PROPOSED] tag
3. **Review with team/user**
4. **Implement after approval**
5. **Update Guided Tours** yang terpengaruh
6. **Update tests**

---

## 💰 MENU KEUANGAN, AKUNTANSI & PAJAK, DAN SDM (MN-T1 — ditulis ulang dari konfigurasi)

Sumber kebenaran: `frontend/src/config/navStructure.js` (grup & entri), `hubTabs.js` (tab), `roles.js` (`ROLE_NAV`),
`viewAliases.js` (alamat lama) dan katalog modul akses `backend/access_modules.py` (menu peran kustom & penyaring izin).
Tabel di bawah dibangkitkan dari konfigurasi itu (menu Sidebar per peran bawaan dengan izin server bawaan, 14 Nov 2026).
Peran: A admin · M manager · F finance · S sales · SA sales_admin · G warehouse · GA warehouse_admin (peran lain tidak
melihat ketiga grup ini). Keuangan **5 entri** + Akuntansi & Pajak **5 entri** = 10 entri dalam 2 grup (dulu 18 entri
dalam 4 grup); grup "Kas & Aset" dihapus.

| Grup › Entri (id menu) | Tab (view) | Peran bawaan yang melihatnya |
|---|---|---|
| Keuangan › Beranda Keuangan (`finance-tower`) | Perlu Tindakan (`finance-desk`) | A M F |
| Keuangan › Beranda Keuangan (`finance-tower`) | Posisi (`finance-tower`) | A M F |
| Keuangan › Beranda Keuangan (`finance-tower`) | Analisis (`bi-finance`) | A M F |
| Keuangan › Piutang (`ar-aging`) | Saldo & Umur (`ar-aging`) | A M F |
| Keuangan › Piutang (`ar-aging`) | Penagihan & Penerimaan (`collection-worklist`) | A M F S SA |
| Keuangan › Piutang (`ar-aging`) | Rencana & Denda (`payment-plans`) | A M F |
| Keuangan › Piutang (`ar-aging`) | Titipan & Saldo Kredit (`customer-credit`) | A M F |
| Keuangan › Piutang (`ar-aging`) | Kredit & Plafon (`credit-overrides`) | A M F |
| Keuangan › Piutang (`ar-aging`) | Kasus (`finance-cases`) | A M F S SA |
| Keuangan › Hutang (`accounts-payable`) | Tagihan (`vendor-bills`) | A M F |
| Keuangan › Hutang (`accounts-payable`) | Kontrabon (`contra-bons`) | A M F G GA |
| Keuangan › Hutang (`accounts-payable`) | GR/IR (Diterima Belum Ditagih) (`gr-ir`) — PK-28; kliring butuh `accounting.manage` | A M F |
| Keuangan › Kas & Bank (`cash-bank`) | Rekening & Saldo (`bank-accounts`) | A M F |
| Keuangan › Kas & Bank (`cash-bank`) | Transaksi Kas (`cash-management`) | A M F |
| Keuangan › Kas & Bank (`cash-bank`) | Rekonsiliasi (`bank-reconciliation`) | A M F |
| Keuangan › Kas & Bank (`cash-bank`) | Kas Kecil (`petty-cash`) — PK-24: Finance & Manajer mencairkan PD (`cash_advance.disburse`), membayar reimburse & menerima pengembalian sisa (`cash_settlement.pay`) | A M F S SA |
| Keuangan › Antar-PT (`interco-transactions`) | — (view `interco-transactions`) | A M F SA G GA |
| Akuntansi & Pajak › Buku Besar (`ledger`) | Jurnal (`general-ledger`) | A M F |
| Akuntansi & Pajak › Buku Besar (`ledger`) | Bagan Akun (`chart-of-accounts`) | A M F |
| Akuntansi & Pajak › Tutup Buku (`closing`) | Daftar Periksa & Tutup (`closing`) | A M |
| Akuntansi & Pajak › Tutup Buku (`closing`) | Buka Periode (`period-unlock`) | A M |
| Akuntansi & Pajak › Tutup Buku (`closing`) | Posting Gagal (`posting-failures`) | A M |
| Akuntansi & Pajak › Laporan (`fin-reports`) | Laba-Rugi, Neraca & Arus Kas (`financial-statements`) | A M |
| Akuntansi & Pajak › Laporan (`fin-reports`) | Profitabilitas (`profitability`) | A M |
| Akuntansi & Pajak › Laporan (`fin-reports`) | Proyeksi Kas (`cashflow-forecast`) | A M |
| Akuntansi & Pajak › Laporan (`fin-reports`) | Anggaran (`budget`) | A M |
| Akuntansi & Pajak › Laporan (`fin-reports`) | Konsolidasi (`consolidation`) | A M |
| Akuntansi & Pajak › Pajak (`tax-hub`) | Faktur Keluaran (`tax-invoices`) | A M F |
| Akuntansi & Pajak › Pajak (`tax-hub`) | Faktur Masukan (`input-tax`) | A M |
| Akuntansi & Pajak › Pajak (`tax-hub`) | PPN & PPh (`cs-pajak`) | A M |
| Akuntansi & Pajak › Aset Tetap (`fixed-assets`) | — (view `fixed-assets`) | A M |
| SDM › Karyawan (`hr-people`) | Karyawan (`hr-employees`) | A M |
| SDM › Karyawan (`hr-people`) | Struktur Organisasi (`hr-org-units`) | A M |
| SDM › Kehadiran (`hr-attendance-hub`) | Presensi (`hr-attendance`) | A M |
| SDM › Kehadiran (`hr-attendance-hub`) | Cuti & Izin (`hr-leave`) | A M |
| SDM › Kehadiran (`hr-attendance-hub`) | Lembur (`hr-overtime`) | A M |
| SDM › Kehadiran (`hr-attendance-hub`) | Lacak Lapangan (`hr-live-tracking`) | A M |
| SDM › Penggajian (`hr-payroll-hub`) | Proses Gaji (`hr-payroll-runs`) | A M |
| SDM › Penggajian (`hr-payroll-hub`) | Slip Gaji (`hr-payslips`) | A M |
| SDM › Penggajian (`hr-payroll-hub`) | Setoran Kewajiban (`hr-payroll-remittances`) — PK-22: hutang BPJS & PPh 21 per masa, Catat Setoran (`payroll.pay`) | A M |
| SDM › Kinerja & Insentif (`hr-kpi-hub`) | Kinerja Sales (`sales-performance`) | A M S SA |
| SDM › Kinerja & Insentif (`hr-kpi-hub`) | Target & Aturan (`incentive-rates`) | A M |
| SDM › Kinerja & Insentif (`hr-kpi-hub`) | Skema (Arsip) (`incentive-schemes`) | A M |
| SDM › Kinerja & Insentif (`hr-kpi-hub`) | KPI Karyawan (`cs-kpi`) | A M |

Dipindah ke luar keuangan: **Pembelian › Pesanan Pembelian › Landed Cost** (`landed-cost`, A M; hub kini 7 tab — baseline
INV-UI-13) dan **Gudang & Logistik › Kendaraan** (`vehicle-logs`, A M G S). CRM & Pelanggan tinggal tiga sub-tab
(Pelanggan · Prospek · Interaksi). Pengaturan › Penjualan tidak lagi memuat Komisi & Insentif; Finance kini melihat
Pengaturan › Keuangan & Pajak › Pemetaan Akun (izin `gl_mapping`).

Alamat lama (`config/viewAliases.js`, `since: "MN-T1"`; rute cadangan `activeView === "<lama>"` tetap; palet Ctrl+K
menampilkan "nama lama → kini di …"):

| Id lama | Mendarat di | Preset |
|---|---|---|
| `advance-report` (Uang Muka Pelanggan) | Keuangan › Piutang › Titipan & Saldo Kredit (`customer-credit`) | `{bagian: "titipan"}` |
| `store-credit` (Saldo Kredit) | idem | `{bagian: "saldo"}` |
| `cash-advances` (Pengajuan Dana) | Keuangan › Kas & Bank › Kas Kecil (`petty-cash`) | `{bagian: "pengajuan"}` |
| `settlements` (Pertanggungjawaban) | idem | `{bagian: "pertanggungjawaban"}` |
| `reimburse-payables` (Hutang Reimburse) | idem (chip dengan `cash_settlement.view` — PK-24, dulu `accounting.view`) | `{bagian: "reimburse"}` |
| `kas-aset` (id grup lama, `legacy`) | Keuangan › Kas & Bank › Kas Kecil | — |

Id yang tetap tetapi berpindah induk: `finance-desk` (kini tab pertama Beranda Keuangan; beranda peran Finance tetap,
menu yang disorot `finance-tower`), `period-unlock`, `posting-failures` (tab Tutup Buku), `payment-plans`,
`finance-cases` (tab Piutang), `interco-transactions` (Keuangan), `fixed-assets` (Akuntansi & Pajak), `incentive-rates`
(SDM › Kinerja & Insentif). Penjaga: `verify_access_catalog_nav.py`, `verify_view_aliases.py`, `verify_desk_targets.py`,
`verify_page_tabs.py` (INV-UI-12/13/14), jest `roleReach.test.js`, `serverAccessReach.test.js`, `navAccess.test.js`,
`mnt1MenuKeuangan.test.js`.

## ⚙️ MENU PENGATURAN (KP-T9 — sembilan hub, ditulis dari konfigurasi)

Sumber: `frontend/src/config/navStructure.js` (grup `settings-hub`), `hubTabs.js`, `backend/access_modules.py` (blok
`KP-T9`). Urutan hub mengikuti cara mengisi PT baru: PT → orang → persetujuan → aturan per bagian → dokumen → sistem. Tanpa
sub-judul; 9 hub, 35 tab tampak, paling banyak 6 per hub (INV-UI-13). Kolom peran = `roles` tab untuk peran bawaan
(A admin · M manajer · F finance · SA admin sales · GA admin gudang · MD · MQ MD quality · QC); Admin Sales mendapat
Penjualan › Kebijakan Retur lewat `ROLE_NAV`. Peran kustom mendapat tab dari modul akses pemilik izin endpoint layarnya;
modul yang memuat tab Pengaturan juga memuat hub induknya dan `settings-hub` (`verify_access_catalog_nav.py` aturan 3–4).
Dengan izin server, manajer tidak melihat Peran & Hak Akses / Cek Peran (tanpa izin `permission`).

| Menu | Tab (view) | Peran bawaan |
|---|---|---|
| Pengaturan › Perusahaan (PT) (`settings-company`) | Profil PT (`settings-pt-profile`) · ikut tersembunyi bersama `entities-access` | A M |
| Pengaturan › Perusahaan (PT) (`settings-company`) | Kesiapan PT (`settings-pt-readiness`) · ikut tersembunyi bersama `entities-access` | A M |
| Pengaturan › Perusahaan (PT) (`settings-company`) | Master per PT (`entity-masters`) | A M |
| Pengaturan › Pengguna & Hak Akses (`settings-access`) | Akun (`settings-accounts`) · ikut tersembunyi bersama `entities-access` | A M |
| Pengaturan › Pengguna & Hak Akses (`settings-access`) | Peran & Hak Akses (`permission-matrix`) · ikut tersembunyi bersama `entities-access` | A M |
| Pengaturan › Pengguna & Hak Akses (`settings-access`) | Cek Peran (`settings-role-check`) · ikut tersembunyi bersama `entities-access` | A M |
| Pengaturan › Persetujuan (`settings-approval`) | Aturan Persetujuan (`approval-rules`) | A M |
| Pengaturan › Persetujuan (`settings-approval`) | Persetujuan R&D (`rnd-divisions`) | A M |
| Pengaturan › Persetujuan (`settings-approval`) | Ketegasan, Pengingat & Dokumen (`settings-cfg-approval`) | A M |
| Pengaturan › Persetujuan (`settings-approval`) | Kontrol dua orang (`settings-dual-control`) | A M |
| Pengaturan › Penjualan (`settings-sales`) | Aturan Penjualan (`settings-cfg-sales`) | A M |
| Pengaturan › Penjualan (`settings-sales`) | Kebijakan Retur (`return-policies`) | A M |
| Pengaturan › Penjualan (`settings-sales`) | Alasan Koreksi (`amendment-reasons`) | A M |
| Pengaturan › Gudang, Pembelian & Produksi (`settings-warehouse`) | Aturan Gudang & Mutu (`settings-cfg-warehouse`) | A M |
| Pengaturan › Gudang, Pembelian & Produksi (`settings-warehouse`) | Penerimaan Barang (`settings-receiving-ocr`) | A M GA |
| Pengaturan › Gudang, Pembelian & Produksi (`settings-warehouse`) | Grade Mutu (`grade-master`) | A M MD SA GA MQ QC |
| Pengaturan › Gudang, Pembelian & Produksi (`settings-warehouse`) | Aturan Pembelian & Makloon (`settings-cfg-purchasing`) | A M |
| Pengaturan › Gudang, Pembelian & Produksi (`settings-warehouse`) | R&D & Desain (`settings-cfg-rnd`) | A M |
| Pengaturan › Keuangan & Pajak (`settings-finance`) | Aturan Keuangan & Pajak (`settings-cfg-finance`) | A M |
| Pengaturan › Keuangan & Pajak (`settings-finance`) | Pemetaan Akun (`gl-account-mappings`) | A M F |
| Pengaturan › Keuangan & Pajak (`settings-finance`) | Kategori Beban (`expense-categories`) | A M |
| Pengaturan › Keuangan & Pajak (`settings-finance`) | Bank (`bank-recon-rules`) | A M |
| Pengaturan › SDM (`settings-hr`) | Aturan SDM & Penggajian (`settings-cfg-hr`) | A M |
| Pengaturan › SDM (`settings-hr`) | Shift & Lokasi Absen (`hr-attendance-setup`) | A M |
| Pengaturan › SDM (`settings-hr`) | Mesin Absen (`settings-attendance-devices`) · ikut tersembunyi bersama `settings-devices`, `hr-attendance-setup` | A M |
| Pengaturan › Dokumen & Notifikasi (`settings-documents`) | Template Dokumen (`pdf-templates`) | A M |
| Pengaturan › Dokumen & Notifikasi (`settings-documents`) | Pengingat Otomatis (`scheduler`) | A M |
| Pengaturan › Dokumen & Notifikasi (`settings-documents`) | WhatsApp (`settings-whatsapp`) · ikut tersembunyi bersama `scheduler` | A M |
| Pengaturan › Dokumen & Notifikasi (`settings-documents`) | Penomoran Dokumen (`settings-doc-numbering`) | A M |
| Pengaturan › Sistem (`settings-system`) | Integrasi & Audit (`admin`) | A |
| Pengaturan › Sistem (`settings-system`) | Perangkat RFID (`settings-devices`) · ikut tersembunyi bersama `cs-rfid-devices` | A |
| Pengaturan › Sistem (`settings-system`) | Kamus Aturan Kain (`domain-registry`) | A M |
| Pengaturan › Sistem (`settings-system`) | Impor Data Awal (`client-dataset-import`) | A |
| Pengaturan › Sistem (`settings-system`) | AI & Tampilan (`settings-cfg-system`) | A M |
| Pengaturan › Sistem (`settings-system`) | Cari Semua Pengaturan (`settings-config`) | A M |

Bagian layar wadah lama yang dinaikkan menjadi tab merender komponen yang sama dengan prop `only` (`AppViewRouter.jsx`):
`EntitiesAccessView only="entities" | "readiness" | "accounts" | "roles" | "role-reality"`, `DevicesView only="absen" | "rfid"`,
`SchedulerView only={["jobs","runs"]} | {["wa"]}`. Tab ber-`inheritsHiddenFrom` ikut tersembunyi bila id wadah lamanya ada di
`hidden_views` peran (atau `ROLE_NAV.remove` peran bawaan). Tab dalam yang tersisa (batas atas INV-UI-14, boleh turun oleh
unit pemilik layarnya): Penerimaan Barang (4), Bank (2), Pengingat Otomatis (2), Template Dokumen (2), Shift & Lokasi Absen
(2), Integrasi & Audit (2), Cari Semua Pengaturan (5).

Alamat lama (`config/viewAliases.js`, `since: "KP-T9"`):

| Id lama | Mendarat di | Catatan |
|---|---|---|
| `entities-access` (Badan Usaha & Akses) | Perusahaan (PT) › Profil PT (`settings-pt-profile`) | rute cadangan tetap (bagian "entities") |
| `settings-purchasing` (hub, `legacy`) | Gudang, Pembelian & Produksi › Aturan Pembelian & Makloon | — |
| `settings-rnd` (hub, `legacy`) | Gudang, Pembelian & Produksi › R&D & Desain | — |
| `settings-masters` (hub, `legacy`) | Perusahaan (PT) › Master per PT | — |
| `settings-notify` (hub, `legacy`) | Dokumen & Notifikasi › Pengingat Otomatis | — |

Alias lama yang tetap: `settings-hub` → Grade Mutu; `doc-templates-basic` → Template Dokumen (tab dasar);
`cs-rfid-devices` → Sistem › Perangkat RFID; `settings-cfg-documents` / `settings-cfg-notify` → Persetujuan › Ketegasan,
Pengingat & Dokumen. Pengaturan yang tinggal di luar grup (KP-29) tampil sebagai kartu tautan di bawah daftar kartu
(`SETTINGS_LINKS`, `configGroupViews.js`): Aturan Keuangan & Pajak → Keuangan › Antar-PT (jadwal bayar), Keuangan › Kas &
Bank › Rekening & Saldo, Perusahaan (PT) › Master per PT (syarat pembayaran); Aturan Gudang & Mutu → Gudang & Logistik ›
Data Gudang; WhatsApp → Pusat Dokumen (WhatsApp kirim dokumen). Pemilih PT di kepala aplikasi: **"Semua PT"**.

## 📝 CHANGELOG

### KP-T9 — 14 Nov 2026 (Pengaturan: sembilan hub, satu istilah "PT")
- Grup Pengaturan 12 hub + 2 sub-judul → **9 hub tanpa sub-judul**: Perusahaan (PT) · Pengguna & Hak Akses (baru) ·
  Persetujuan · Penjualan · Gudang, Pembelian & Produksi · Keuangan & Pajak · SDM · Dokumen & Notifikasi · Sistem. Hub
  Pembelian & Produksi, R&D, Master Data, Notifikasi & Penjadwal hilang (alias `legacy`). Rincian: bagian "MENU PENGATURAN
  (KP-T9)" di atas.
- Enam view baru (bagian layar wadah lama): `settings-pt-profile`, `settings-pt-readiness`, `settings-accounts`,
  `settings-role-check`, `settings-attendance-devices`, `settings-whatsapp`; `permission-matrix` kini tab nyata.
- Katalog modul akses: blok `KP-T9` (`_KPT9_NAV_REPLACE/ADD/REMOVE`); label `interco` "Transaksi Antar-PT", modul
  `entities` "Data PT", sumber daya `entity` "PT". Penjaga katalog: aturan (3) dan (4) + `--self-test` (gate statik);
  `check_nav_map.py` CHECK 6 (istilah menu).

### KP-T5 — 14 Nov 2026 (tab Penomoran Dokumen)
- Pengaturan › **Dokumen & Cetak** (hub `settings-documents`) mendapat tab ke-2 **Penomoran Dokumen** (view
  `settings-doc-numbering`, `features/settings/docnumbering/DocNumberingView.jsx`; testid `docnum-view`). Modul akses:
  **Pusat Pengaturan** (`settings`: `nav` + `settings-documents`, `settings-doc-numbering`; tab Template Dokumen tetap
  milik modul Dokumen); layar dibuka izin `settings` (`VIEW_RESOURCE_OVERRIDES`). Baca `settings.view`, ubah
  `settings.manage` (`/api/doc-numbering`). Pilihan "Semua PT" = baris grup.
- Wizard PT langkah 3 (Penomoran & Dokumen): empat contoh nomor dari `POST /api/doc-numbering/preview` (format grup yang
  berlaku, kode = isian wizard).

### MN-T1 — 14 Nov 2026 (menu keuangan & SDM: pindah dan kelompokkan, isi layar tetap)
- Keuangan: **Beranda Keuangan** (Perlu Tindakan · Posisi · Analisis; Meja Finance bukan lagi menu lepas/butir Meja
  Peran) · **Piutang** (6 tab; Penagihan & Kredit dari CRM, Uang Muka + Saldo Kredit = satu tab pembungkus ber-chip,
  Rencana Bayar, Kasus) · **Hutang** (dari Pembelian) · **Kas & Bank** (+ Kas Kecil = pembungkus ber-chip) · **Antar-PT**
  (dari Akuntansi & Pajak). Akuntansi & Pajak: Buku Besar · **Tutup Buku** (3 tab) · Laporan · Pajak · **Aset Tetap**.
  SDM › KPI → **Kinerja & Insentif** (Kinerja Sales, Target & Aturan, Skema (Arsip), KPI Karyawan); Payroll Run →
  **Proses Gaji**. Label: Rekonsiliasi Bank → Rekonsiliasi, Jurnal & Buku Besar → Jurnal, Chart of Accounts → Bagan Akun,
  Profitabilitas & Margin → Profitabilitas, Proyeksi Arus Kas → Proyeksi Kas, Anggaran vs Realisasi → Anggaran,
  Konsolidasi Grup → Konsolidasi, Pajak (PPN & PPh) → PPN & PPh, Tagihan Supplier → Tagihan, Kontrabon (Tukar Faktur) →
  Kontrabon. Rincian & tabel per peran: bagian "MENU KEUANGAN, AKUNTANSI & PAJAK, DAN SDM" di atas.
- `roles` grup: + sales di Keuangan & SDM, + gudang di Keuangan, gudang dicabut dari Akuntansi & Pajak. `ROLE_NAV.finance`
  + 16 id (K-09, K-17, UX-17, IA-06); `ROLE_NAV.sales_admin` tanpa `akuntansi`.
- Katalog modul akses (`backend/access_modules.py`, blok `MN-T1`): menu ikut modul pemilik sumber daya endpoint utama
  layarnya (`_MNT1_NAV_ADD`/`_MNT1_NAV_REMOVE`); `hidden_views` berisi id tak dikenal (mis. `kas-aset`) dibuang saat
  dimuat. Izin bawaan Finance: + `vendor_bill.view/pay`, `contra_bon.view/pay`, `cash_advance.disburse` (Manajer juga
  `cash_advance.disburse`).
- Penjaga baru di `verify_page_tabs.py`: INV-UI-13 (maks 6 tab tampak per hub; baseline `hub_tab_limit.json`) dan
  INV-UI-14 (tanpa tab tingkat ketiga; baseline `third_level_tabs.json`).

### PR-T5 — 14 Nov 2026 (pemilik menu & tab di katalog modul akses)
Tidak ada menu baru; yang berubah = modul akses (`backend/access_modules.py`) yang MEMBUKA menu/tab untuk peran kustom
dan menyaring menu peran lain (`view_resources`).
- Modul gabungan "Pengaturan, Pengguna & Hak Akses" (`admin`) dipecah lima: **Akun Pengguna** (`accounts`: `settings-hub`,
  `settings-company`, `entities-access`), **Peran & Hak Akses** (`roles`: idem), **Badan Usaha (PT)** (`entities`: idem +
  `settings-masters`, `entity-masters`), **Pusat Pengaturan** (`settings`: `settings-system`, `settings-config`,
  `settings-cfg-system`, `admin`, `settings-approval`, `approval-rules`, `settings-cfg-approval`, `settings-dual-control`,
  `settings-masters`, `domain-registry`, `settings-documents`, `settings-cfg-documents`, `settings-notify`,
  `settings-cfg-notify`), **Penjadwal & Notifikasi Otomatis** (`scheduler`: `settings-notify`, `scheduler`). Id lama
  `admin` tetap diterima sebagai alias kelimanya.
- `pdf-templates` dan grup `settings-documents` → modul **Dokumen, Cetak & Tanda Tangan**; `settings-devices` tetap milik
  Operasi Gudang, SDM, dan Perangkat.
- Menu/tab yang dulu di luar katalog: `sales-admin-desk` → Pesanan Penjualan; `finance-desk` → Uang Masuk, Piutang &
  Faktur Pajak; `md-desk` → Desain & Desainer; `warehouse-admin-desk` → Operasi Gudang; `sample-admin-desk` → Pesanan
  Sample; grup `meja-peran` → kelimanya. Meja peran tampil hanya bila aksinya dipegang (`view_actions`: Konfirmasi
  pesanan · Putuskan selisih bayar · Lihat permintaan desain · Lihat operasi gudang · Lihat pesanan sample). Tab
  `customers-master` → Pelanggan & CRM; `internal-prices` → Transaksi Antar Badan Usaha; `reimburse-payables` → Kas Kecil;
  `amendment-reasons`, `bank-recon-rules` → Kas, Bank & Kasus Keuangan; `settings-receiving-ocr` → Operasi Gudang.
- `home` dan `my-desk` tidak masuk modul: untuk peran kustom tampil menurut sifat peran (halaman awal ber-menu `home`;
  kategori kerja terisi). `permission-matrix` (alias), `cs-bom`, `hr-my-profile` tidak berubah.

### KF-T4 — 14 Nov 2026 (Pengaturan: 13 kelompok bersub-judul, dua tab jadi alias)
- Registry Pengaturan kini 13 kelompok bersub-judul (`backend/config_registry.py` `GROUPS`); delapan layar
  `settings-cfg-*` (`features/settings/config/configGroupViews.js`). Id kelompok lama diterima lewat `GROUP_ALIASES`.
- Tab dicabut, id tetap (rute cadangan `activeView === "<id>"` + `access_modules.py`): **Aturan Dokumen**
  (`settings-cfg-documents`, hub `settings-documents`) → alias ke `settings-cfg-approval` preset `{section:
  "rujukan-dokumen"}`; **Penerima Notifikasi** (`settings-cfg-notify`, hub `settings-notify`) → alias ke
  `settings-cfg-approval` preset `{section: "pemberitahuan"}` (`config/viewAliases.js`).
- Label tab: `settings-cfg-approval` "Persetujuan & Ambang" → **Ketegasan, Pengingat & Dokumen**; `settings-cfg-system`
  "Tampilan & Asisten" → **AI & Tampilan**. Judul halaman delapan layar = "<label tab> · <label kelompoknya>"
  (`config/navMeta.js`). Semua pengaturan: tab "Kesehatan Konfigurasi" → **Kesehatan Pengaturan**.
- Pengaturan › Gudang & Mutu › **Penerimaan & OCR** membaca preset `{tab}` (kartu "Cara mencatat barang datang" menautkan
  ke tab Mode Penerimaan).

### KF-T6 — 14 Nov 2026 (tab Kontrol dua orang)
- Pengaturan › **Persetujuan** (hub `settings-approval`) mendapat tab ke-4 **Kontrol dua orang** (view
  `settings-dual-control`, `features/settings/kontrol/DualControlView.jsx`; testid `dual-control-view`). Modul akses:
  Admin (`nav` modul `admin`); layar dibuka izin `settings` (`VIEW_RESOURCE_OVERRIDES`). Baca `settings.view`, ubah
  `settings.manage` (lewat `PUT /api/config/values`). Kunci `kontrol.*` disembunyikan dari tab "Persetujuan & Ambang"
  (tautan ke tab baru); deep link kunci `kontrol.*` mendarat di tab ini.
- Buku Besar › **Jurnal**: saringan **Menunggu persetujuan** (`gl-journal-pending-filter`) + pita
  "{n} jurnal manual menunggu orang kedua" (`gl-proposal-banner`); tombol Setujui/Tolak per usulan (bukan menu baru).
- Tutup Buku: label "Menunggu orang kedua — diajukan {nama}" (`closing-reopen-pending-{id}`) pada periode yang
  pengajuan buka kembalinya menunggu orang kedua.

### v1.0 — 23 Mei 2026 (Initial Navigation Map)
- Created navigation hierarchy untuk 9 major sections
- Defined role-based access matrix (4 roles)
- Documented WMS tabs (5 tabs) & Orders tabs (2 tabs)
- Established data-testid naming convention
- Set navigation-first policy

---

## 🆕 TARGET GROUPED NAVIGATION IA (selaras KN_14 — 6 Fase)

> **Sumber:** `KN_14_INFORMATION_ARCHITECTURE.md` §5. Menu **flat eksisting** akan
> berevolusi menjadi **grouped domains** agar scale untuk 6 fase. Tanda: ✅ ada ·
> 🟡 enhancement · 🆕 [PLANNED]. **Belum diimplementasi** — IA difinalkan dulu.

```
GLOBAL SHELL (Top Bar)
  ├── Entity Switcher 🆕   (konteks entitas aktif: PT Kain Suka Cita / CV Kanda Suka / Semua)
  ├── 🔔 Notification Center 🆕
  ├── ❓ Help & Tours ✅
  └── 👤 User Menu ✅

SIDEBAR (grouped, collapsible, role-filtered)
  🏠 Beranda (role landing) ✅
  💼 Penjualan
     ├── POS / Sales Portal ✅
     ├── Pesanan Penjualan (SO) ✅🟡 (status: Pending/Keep/Ready/Waiting Shipment/Partial/Complete)
     ├── Price List per Customer 🆕
     ├── Approval Harga (negosiasi + upload bukti + approval owner) 🆕
     ├── Returns & BS 🆕
     ├── Special Order (OD) 🆕
     └── Faktur & Pajak Jual 🆕
  🧾 Pembelian
     ├── Pesanan Pembelian (PO) ✅🟡
     ├── Suppliers (Master) 🆕
     ├── Approval Pembelian 🆕
     ├── BOM Printing 🆕
     └── Pengelolaan Kas 🆕
  🏭 Gudang
     ├── Stok & Inventori ✅
     ├── Inbound / Penerimaan ✅ (toleransi ±2% 🆕)
     ├── Outbound / Pengiriman ✅
     ├── Transfer Antar Gudang ✅
     ├── Cycle Count ✅
     └── Stock Analytics (fast/slow/dead >3bln) 🆕
  📡 RFID
     ├── Lokasi RFID 🆕 · Tags 🆕 · Devices 🆕 · Gate Monitor (green/red) 🆕
  💰 Keuangan ✅ (MN-T1 — susunan berlaku: bagian "MENU KEUANGAN, AKUNTANSI & PAJAK, DAN SDM")
     ├── Beranda Keuangan · Piutang · Hutang · Kas & Bank (+ Kas Kecil) · Antar-PT
  🧮 Akuntansi & Pajak ✅ (MN-T1)
     ├── Buku Besar · Tutup Buku · Laporan · Pajak · Aset Tetap
  (💼 Kas & Aset — DIHAPUS MN-T1: Kas Kecil → Keuangan › Kas & Bank, Kendaraan → Gudang & Logistik, Aset Tetap →
     Akuntansi & Pajak; alamat `?view=kas-aset` → Kas Kecil)
  👥 SDM (HRD) ✅
     ├── Karyawan · Kehadiran · Penggajian (Proses Gaji · Slip Gaji · Setoran Kewajiban — PK-22) · Kinerja & Insentif (MN-T1)
  📊 Analitik (BI)
     └── Sales / Stock / Finance / HR dashboards 🆕
  📝 Dokumen
     ├── Print Center ✅ · Templates ✅
  ⚙️ Admin & Master Data
     ├── Business Entities 🆕 · Customers ✅ · Products ✅🟡 · Warehouses ✅🟡 (Zone→Rack→Level🆕→Bin)
     ├── UOMs ✅ · Users ✅ · Permissions ✅ · Audit ✅ · System Settings 🆕
  🔔 Eskalasi ✅

ROUTE STANDALONE (tanpa login)
  ├── /discovery/{session_id} ✅
  └── /catalog[/{product_id}] 🆕 (Ecommerce katalog publik — read-only)
```

**Aturan kedalaman:** Grup (L1) → Menu (L2) → Tab/Panel (L3) → Modal (L4). Maks 4.
**data-testid:** `nav-group-{domain}`, `nav-{module}`, `tab-{module}-{tab}`, `entity-switcher`, `notif-bell`.

> ⚠️ Migrasi menu flat → grouped = bagian Fase 0/1 (implementasi DITUNDA). Saat
> dieksekusi, update bagian ini dari [PLANNED] → aktif + sinkronkan Guided Tours.

---

**Maintained by:** Development Team  
**Review Cycle:** Per major feature release  
**Next Review:** Setelah Phase 4 (Tier 1 ERP modules)  
**IA induk:** `KN_14_INFORMATION_ARCHITECTURE.md` (SSOT triangle: KN_14 ⇄ KN_13 ⇄ ENTITY_REGISTRY)

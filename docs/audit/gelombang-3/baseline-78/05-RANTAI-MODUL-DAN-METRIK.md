# Rantai bisnis, sumber data dan konsekuensi

Diagram berikut memetakan jalur yang ditelusuri dan titik masalah, bukan klaim seluruh permutasi flow sudah diuji end-to-end.

## Penjualan sampai kas

```text
Customer/term → SO/price → fulfillment decision → reserve/PR → PO atau makloon → receive → RFID/tag → putaway/transit → picking/cut → loading perwarehouse → SJ/dispatch → revenue/COGS/AR → receipt/deposit → bank match → reversal
```

**Catatan terkait:** D4-SALES-01/02/03; D4-FIN-02/03/04; V3-AR-01; V3-BANK-01; V3-CUT-01; V3-WMS-02; V3-RFID-01.

Kesalahan scope target/komisi; reservasi parsial tidak tampak di analitik; loading SO-wide; fault window receipt dan cut. Shipping GL tidak dapat diasumsikan salah hanya dari laporan SO-based.

## MD/R&D ke SKU dan produksi

```text
Role line×sampling → round labdip/proofing/handfeel → result/spec/final ACC → SKU/color/lot → material stage → PR/raw reservation → production issue → output/cost → sale
```

**Catatan terkait:** REQ-01/03/05/08; D4-RND-01; V3-MRES-01/02; V3-PROD-01/02; V3-MKO-01.

SKU MD wajib proses sesuai lini; raw material greige/benang tidak wajib uji sama. Masih perlu keputusan rule hard-gate vs authorized override. Producer menyimpan performer ID tetapi KPI masih nama.

## Pembelian dan selisih roll

```text
PO perroll/perlength → receiving actual lengths → shortage/overage notice → wait/close/amend → supplier bill/payment → return → cost adjustment
```

**Catatan terkait:** V3-PO-01/02/03; D4-STOCK-03; D4-AI-01.

Task variance stale, amendreceivedqty guard dan perubahan notes dapat menutup task. Analytics AP fallback tidak sama dengan bill canonical.

## Intercompany dan stok gabungan

```text
Physicalwarehouse + ownerA/B → aggregate catalog visible to sales → ownership procurement/transfer → entitySO fulfillment → separate ledger → analytics owner grouping
```

**Catatan terkait:** D4-STOCK-01; D4-SALES-03; D4-FIN-01; D4-HR-01.

POV totalstock boleh gabungan sesuai kebutuhan klien; financial/legalownership tidak boleh hilang. Grain row join menyebabkan nilai/velocity duplikasi walau qty correct.

## Reservasi, potong dan transformasi

```text
Whole/partial reserve → pendingcut → physical parent split → child RFID verify → release/pick/ship → WAC/weight/value conservation → snapshot
```

**Catatan terkait:** V3-WEIGHT-01; V3-CUT-01; D4-AI-05/06; D4-DASH-01.

Live availability, canonicalbalance dan historicalfact harus satu definisi. Meter/kg tidak bisa digabung menjadi grandquantity.

## Cycle count dan kesehatan gudang

```text
Read → incident → countopen → assess → approve/journal → device heartbeat → health day/last accuracy
```

**Catatan terkait:** D4-WMS-01/02/03; V3-MASTER-01.

Day boundaryUTC salahWIB; lastopen bukan lastmeasured; rack.levels capacity tidak dibaca. Hardware tetap belumdiuji.

## Keuangan dan pelaporan

```text
GL posting/reversal/close → BS/PL/CF → AR/AP aging → tower/BI/forecast → cost redaction → dashboard
```

**Catatan terkait:** V3-CF-01; V3-DATE-01; D4-CASH-01; D4-FIN-01/02/03/04.

Net cash dapat benar tetapi klasifikasi arus kas salah; default scope Tower tidak konsisten. Estimasi menggunakan WAC terkini berbeda dari realisasi historis. Hipotesis redacted-cost tidak dijadikan temuan UI normal; lihat dokumen 08.

## HR/payroll/sales commission

```text
Employee lifecycle → attendance/overtime → payrollrun → incentive accrual → post/pay → HR analytics
```

**Catatan terkait:** D4-HR-01/02; D4-SALES-03.

Aggregatepayrollreport salah tidak membuktikan posting GL salah. Turnover membutuhkan effective separationevent, bukan updated_at.

## Marketing dan AI analytics

```text
Postmulti-account → aggregatemetrics → channel breakdown → salesfact attribution → unit/date/line scope → daily snapshot → Tanya KN response
```

**Catatan terkait:** D4-MKT-01; D4-AI-01/02/03/04/05/06.

Perchannel actualmeasurements belum tersedia; ETLdelete-before-insert dapat menghapus readmodel. Factmoneyrounding tidakmengonservasi netorder.

## Frontend state dan pengalaman data

```text
Selected entity/period → parallel requests → response generation → table/chart/KPI → tooltip/export/print
```

**Catatan terkait:** D4-FE-01/02; D4-WMS-02.

Respons periode lama dapat menimpa periode baru pada entitas yang sama; App.js meremount saat entitas berubah; chart dipotong menjadi 14 hari; cycle count belum terukur memerlukan status dan penanganan null. Uji browser aktual belum dilakukan.

## Inventaris consumer frontend

1477 literal API calls tersedia pada `frontend-api-lineage.csv`; 21 file terdeteksi memakai komponen chart. Mapping literal dapat melewatkan dynamic router/service call, sehingga label unresolved dipertahankan. Semua 5824 file ada di `all-file-coverage.csv`. Hash atau handler match bukan tanda data metric benar.

- `frontend/src/config/hubTabs.js`: Chart.
- `frontend/src/config/navMeta.js`: Chart.
- `frontend/src/config/navStructure.js`: PieChart.
- `frontend/src/features/designer/DesignScoreTrendChart.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/designer/DesignerKpiTrendChart.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/finance/BiFinanceView.jsx`: BarChart, Chart, ResponsiveContainer.
- `frontend/src/features/finance/BudgetView.jsx`: BarChart, ResponsiveContainer.
- `frontend/src/features/finance/CashFlowForecastView.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/finance/CashFlowTab.jsx`: BarChart, ResponsiveContainer.
- `frontend/src/features/finance/ChartOfAccounts.jsx`: Chart.
- `frontend/src/features/finance/EquityChangesTab.jsx`: BarChart, ResponsiveContainer.
- `frontend/src/features/finance/FinanceTowerParts.jsx`: BarChart, PieChart, ResponsiveContainer.
- `frontend/src/features/finance/ProfitabilityView.jsx`: BarChart, ResponsiveContainer.
- `frontend/src/features/home/SalesHome.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/hr/HrAnalyticsView.jsx`: BarChart, LineChart, PieChart, ResponsiveContainer.
- `frontend/src/features/inventory/StockAnalyticsView.jsx`: BarChart, PieChart, ResponsiveContainer.
- `frontend/src/features/logistics/DispatchDashboard.jsx`: PieChart, ResponsiveContainer.
- `frontend/src/features/manager/ManagerDashboard.jsx`: BarChart, LineChart, PieChart, ResponsiveContainer.
- `frontend/src/features/sales/mobile/MobileSalesHome.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/tanya/TanyaChart.jsx`: AreaChart, BarChart, LineChart, PieChart, ResponsiveContainer.
- `frontend/src/features/tanya/TanyaCostChart.jsx`: BarChart, ResponsiveContainer.

## Pemenuhan baru dan metrik pesanan

Catatan PLAN-01/02/03/04/05, GLOBAL-01, SUPPLY-01, BACKORDER-01 dan CAP-01 menghubungkan keputusan pemenuhan, PR/PO, incoming, reservasi demand dan KPI. Rincian contoh rantai dan dampak patch tersedia pada dokumen 12.

D4-ORDER-01 menelusuri original public dashboard window 20 dan summary seluruh order hingga useMemo frontend: revenue sudah benar, count dan denominator rata-rata belum benar. Top Customers, status/pending/expiry masih memakai window lokal; Recent Orders 10 memang berlabel subset. Register 21 file chart ada pada latest/evidence/frontend-chart-register.csv. Numeric non-chart views juga ditelusuri pada API lineage dan temuan. Register statis tidak diberi status seluruh angka rendered telah benar.

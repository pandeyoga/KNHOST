// Keputusan pemilik 26 Okt (audit UI tahap 2) — wilayah D2: K-05 (Analitik Stok moving average), K-04 (Stok rendah
// definisi tunggal), K-06 + B2 (KPI "Menunggu persetujuan"), B1 (SPK "Diterima seluruhnya" + roll ditahan),
// B3 (grade per roll di timeline retur).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import StockAnalyticsView, { fmtCoverage, fmtMa } from "../inventory/StockAnalyticsView";
import OrderDashboard from "../orders/OrderDashboard";
import InspectionDetailPanel from "../inspections/InspectionDetailPanel";
import ReturnTimelinePanel from "../sales/ReturnTimelinePanel";
import InventorySummaryCards from "../wms/inventory/InventorySummaryCards";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => ({ value, onValueChange, options = [], "data-testid": tid }) => (
  <select data-testid={tid} value={value} onChange={(e) => onValueChange(e.target.value)}>
    <option value="" />
    {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
jest.mock("recharts", () => {
  const Box = ({ children }) => <div>{children}</div>;
  return { ResponsiveContainer: Box, PieChart: Box, Pie: Box, Cell: () => null, BarChart: Box, Bar: () => null,
    XAxis: () => null, YAxis: () => null, CartesianGrid: () => null, Tooltip: () => null };
});
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../inspections/InspectLineModal", () => () => null);
jest.mock("../inspections/InspectSheetGrid", () => () => null);
jest.mock("../../services/confirmService", () => ({ askReason: jest.fn(), askConfirm: jest.fn() }));
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn() }));
jest.mock("../inspections/inspectionsApi", () => ({
  ...jest.requireActual("../inspections/inspectionsApi"),
  finishInspection: jest.fn(),
}));
const axios = require("../../services/apiClient").default;
const api = require("../inspections/inspectionsApi");
const confirm = require("../../services/confirmService");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}
const pick = async (el, value) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
};
afterEach(() => { jest.clearAllMocks(); document.body.innerHTML = ""; });

// ── K-05 ──────────────────────────────────────────────────────────────────────
const ANALYTICS = {
  thresholds: { velocity_window_days: 90, trend_window_days: 30, best_seller_pct: 20, slow_moving_pct: 20,
    new_sku_age_days: 90, coverage_cap_days: 365, trend_band_pct: 10 },
  method: { basis: "moving_average_so", rank_groups: [{ unit: "yard", ranked: 12 }, { unit: "kg", ranked: 3 }],
    class_labels: { best: "Best seller", normal: "Normal", slow: "Slow moving", dead: "Tidak bergerak", new: "Baru" } },
  summary: { sku_count: 3, total_on_hand_value: 5e6, total_landed_value: 0, stock_out_skus: 1, aging_buckets: [],
    by_class: { best: { count: 1, value: 0 }, normal: { count: 0, value: 0 }, slow: { count: 1, value: 2e6 },
      dead: { count: 1, value: 3e6 }, new: { count: 0, value: 0 } } },
  rows: [
    { product_id: "p1", sku: "Y1", product_name: "Kain laris", unit: "yard", classification: "best", on_hand_qty: 0,
      stock_out: true, value: 0, ma_daily: 12.5, ma_trend_daily: 20, trend: "naik", percentile: 95.83, rank_group_size: 12,
      sold_qty_window: 1125, days_of_supply: 0, days_since_sale: 1, warehouses: [] },
    { product_id: "p2", sku: "Y2", product_name: "Kain lambat", unit: "yard", classification: "slow", on_hand_qty: 5000,
      value: 2e6, ma_daily: 0.004, ma_trend_daily: 0, trend: "turun", percentile: 4.17, rank_group_size: 12,
      sold_qty_window: 0.36, days_of_supply: 1250000, days_since_sale: 60, warehouses: ["Jakarta"] },
    { product_id: "p3", sku: "K1", product_name: "Benang diam", unit: "kg", classification: "dead", on_hand_qty: 80,
      value: 3e6, ma_daily: 0, ma_trend_daily: 0, trend: null, percentile: null, rank_group_size: 0,
      sold_qty_window: 0, days_of_supply: null, days_since_sale: null, warehouses: ["Bandung"] },
  ],
};

test("K-05 formatter: coverage dibatasi > 365 hari, MA kecil tetap terbaca", () => {
  expect(fmtCoverage(null)).toBeNull();
  expect(fmtCoverage(1250000)).toBe("> 365 hari");
  expect(fmtCoverage(30)).toBe("30 hari");
  expect(fmtMa(0)).toBe("0");
  expect(fmtMa(0.004)).toBe("< 0,01");
  expect(fmtMa(12.5)).toBe("12,5");
});

test("K-05 Analitik Stok: 5 kelas, dasar metode, MA/persentil/tren per satuan, coverage dibatasi", async () => {
  axios.get.mockImplementation((url) => Promise.resolve({ data: url === "/api/inventory/stock-analytics" ? ANALYTICS : [] }));
  const { host, root } = await mount(<StockAnalyticsView selectedEntity="ent_ksc" />);
  const method = q(host, "sa-method").textContent;
  expect(method).toMatch(/moving average penjualan 90 hari/);
  expect(method).toMatch(/ABC\/Pareto/);
  expect(method).toMatch(/FSN/);
  expect(method).toMatch(/yard 12 SKU · kg 3 SKU/);
  for (const c of ["best", "normal", "slow", "dead", "new"]) expect(q(host, `sa-kpi-${c}`)).not.toBeNull();
  expect(q(host, "sa-kpi-best").textContent).toMatch(/Best seller/);
  expect(q(host, "sa-kpi-dead").textContent).toMatch(/Tidak bergerak/);
  expect(q(host, "sa-stockout-p1").textContent).toBe("stok habis");
  expect(q(host, "sa-pct-p1").textContent).toMatch(/P96.*dari 12 SKU yard/);
  expect(q(host, "sa-trend-p1").textContent).toMatch(/naik/);
  expect(q(host, "sa-ma-p2").textContent).toMatch(/< 0,01 yard\/hari/);
  expect(q(host, "sa-cover-p2").textContent).toBe("> 365 hari");
  expect(q(host, "sa-row-p3").textContent).toMatch(/tanpa penjualan/);
  // klik kartu kelas = saring baris
  await act(async () => { q(host, "sa-kpi-dead").click(); });
  expect(q(host, "sa-row-p3")).not.toBeNull();
  expect(q(host, "sa-row-p1")).toBeNull();
  await act(async () => { root.unmount(); });
});

// ── K-04 ──────────────────────────────────────────────────────────────────────
test("K-04 kartu Stok Rendah menyebut cakupan definisi tunggal", async () => {
  const { host, root } = await mount(<InventorySummaryCards onHandByUnit={{ yard: 10 }} availByUnit={{ yard: 5 }}
    reservedByUnit={{}} lowCount={7} lowHint="produk · tersedia < 100 · seluruh badan usaha" availHint="Tersedia = papan stok" />);
  expect(q(host, "summary-card-stok-rendah").textContent).toMatch(/7/);
  expect(q(host, "summary-card-hint").textContent).toMatch(/tersedia < 100/);
  expect(q(host, "summary-card-tersedia").getAttribute("title")).toBe("Tersedia = papan stok");
  await act(async () => { root.unmount(); });
});

// ── K-06 + B2 ─────────────────────────────────────────────────────────────────
test("K-06 KPI Pesanan = Menunggu persetujuan saja (bukan + Dipesan + Disetujui)", async () => {
  const summary = { pending_count: 4, pending_basis: "Pesanan berstatus Menunggu persetujuan · semua tanggal · tanpa pesanan sample",
    by_status: { waiting_approval: { count: 4 }, reserved: { count: 9 }, approved: { count: 2 } }, expiring_soon_count: 0,
    periods: { "7d": { revenue: 0, fulfilled_count: 0, orders: 0, by_status: {}, avg_order_value: 0, top_customers: [] } } };
  const { host, root } = await mount(<OrderDashboard orders={[]} summary={summary} />);
  expect(q(host, "order-dashboard-pending-label").textContent).toBe("Menunggu persetujuan");
  expect(q(host, "order-dashboard-pending").textContent).toBe("4");
  expect(q(host, "order-dashboard-pending-breakdown").textContent).toMatch(/tanpa pesanan sample/);
  expect(host.textContent).not.toMatch(/Belum diproses/);
  await act(async () => { root.unmount(); });
});

// ── B1 ────────────────────────────────────────────────────────────────────────
const QC_USER = { role: "qc", permissions: { qc: ["view", "inspect", "release"], inspection: ["view", "decide"] } };
const DECISIONS = [{ value: "terima", label: "Diterima seluruhnya" }, { value: "terima_sebagian", label: "Diterima sebagian" },
  { value: "tolak", label: "Ditolak" }];
const SPK = { id: "ins72", number: "KSC/INS-00072", kind: "makloon_output", status: "in_progress",
  lines: [{ id: "l1", roll_id: "r1", roll_no: "RL-00001" }, { id: "l5", roll_id: "r5", roll_no: "RL-00005" }],
  held_rolls: [{ line_id: "l5", roll_id: "r5", roll_no: "RL-00005", reason: "QC 4-point GAGAL" }] };

test("B1 peringatan (bawaan): Diterima seluruhnya + roll ditahan → dialog; Batal = tidak menutup SPK", async () => {
  api.finishInspection.mockResolvedValue({ ...SPK, status: "done" });
  confirm.askConfirm.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  const { host, root } = await mount(<InspectionDetailPanel doc={SPK} currentUser={QC_USER} onChanged={jest.fn()}
    meta={{ decisions: DECISIONS, policy: { accept_all_with_hold_action: "peringatkan" } }} />);
  await pick(q(host, "ins-decision-select"), "terima");
  expect(q(host, "ins-held-warning").textContent).toMatch(/1 roll masih ditahan\/gagal QC \(RL-00005\)/);
  expect(q(host, "ins-finish-button").disabled).toBe(false);
  await act(async () => { q(host, "ins-finish-button").click(); });
  expect(confirm.askConfirm).toHaveBeenCalledTimes(1);
  expect(confirm.askConfirm.mock.calls[0][0].message).toMatch(/RL-00005/);
  expect(api.finishInspection).not.toHaveBeenCalled();
  await act(async () => { q(host, "ins-finish-button").click(); });
  expect(api.finishInspection).toHaveBeenCalledWith("ins72", "terima", "", {});
  await act(async () => { root.unmount(); });
});

test("B1 setelan blokir: tombol mati + alasan; tanpa roll ditahan tidak ada peringatan", async () => {
  const { host, root } = await mount(<InspectionDetailPanel doc={SPK} currentUser={QC_USER} onChanged={jest.fn()}
    meta={{ decisions: DECISIONS, policy: { accept_all_with_hold_action: "blokir" } }} />);
  await pick(q(host, "ins-decision-select"), "terima");
  expect(q(host, "ins-finish-button").disabled).toBe(true);
  expect(q(host, "ins-held-warning").textContent).toMatch(/diblokir pengaturan QC/);
  await pick(q(host, "ins-decision-select"), "terima_sebagian");
  expect(q(host, "ins-held-warning")).toBeNull();
  await act(async () => { root.unmount(); });
  const clean = { ...SPK, held_rolls: [] };
  const m2 = await mount(<InspectionDetailPanel doc={clean} currentUser={QC_USER} onChanged={jest.fn()}
    meta={{ decisions: DECISIONS, policy: { accept_all_with_hold_action: "blokir" } }} />);
  await pick(q(m2.host, "ins-decision-select"), "terima");
  expect(q(m2.host, "ins-held-warning")).toBeNull();
  expect(q(m2.host, "ins-finish-button").disabled).toBe(false);
  await act(async () => { m2.root.unmount(); });
});

// ── B3 ────────────────────────────────────────────────────────────────────────
test("B3 timeline retur: grade PER ROLL, grade baris hanya cadangan bertanda", async () => {
  const timeline = { summary: { per_unit: [], value_basis: "" }, lanes: {}, events: [], rolls: [
    { roll_id: "ra", roll_no: "RL-31983", qty_claimed: 60.5, unit: "yard", location: "Gudang", qc_actual: 60.5,
      qc_grade: "A", qc_grade_source: "roll", qc_line_grade: "B" },
    { roll_id: "rb", roll_no: "RL-31985-1", qty_claimed: 20, unit: "yard", location: "Gudang", qc_actual: 20,
      qc_grade: "B", qc_grade_source: "roll", qc_line_grade: "B" },
    { roll_id: "rc", roll_no: "RL-1", qty_claimed: 5, unit: "yard", location: "Gudang", qc_actual: 5,
      qc_grade: "C", qc_grade_source: "line", qc_line_grade: "C" }] };
  axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/timeline") ? timeline : [] }));
  const { host, root } = await mount(<ReturnTimelinePanel ret={{ id: "ret1", status: "inspected" }} />);
  expect(q(host, "return-timeline-rolls").textContent).toMatch(/Grade QC/);
  expect(q(host, "return-timeline-rolls").textContent).not.toMatch(/Grade QC baris/);
  expect(q(host, "timeline-roll-grade-ra").textContent).toBe("Abaris: B (terburuk)");
  expect(q(host, "timeline-roll-grade-rb").textContent).toBe("B");
  expect(q(host, "timeline-roll-grade-rc").textContent).toBe("Cgrade baris");
  await act(async () => { root.unmount(); });
});

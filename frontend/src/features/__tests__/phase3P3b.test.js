// Fase 3 · P3 — D-17 satu dasbor pesanan + satu kontrol status, D-14 harga mengikuti PT di header, D-24a Meja
// Cutting (menunggu dipotong = ringkasan + tautan), D-07 Matriks divisi memakai dialog bersama PO Custom.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import OrdersView from "../orders/OrdersView";
import OrderDashboard from "../orders/OrderDashboard";
import ManagerDashboard from "../manager/ManagerDashboard";
import PricelistView from "../sales/PricelistView";
import CuttingDesk from "../samples/CuttingDesk";
import MyApprovalsPanel from "../approvals/MyApprovalsPanel";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { askReason } from "../../services/confirmService";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), isCancel: () => false,
    defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, REASON_MIN_LENGTH: 5,
  askReason: jest.fn(), askConfirm: jest.fn(async () => true), default: {},
}));
jest.mock("../../hooks/usePagedList", () => ({
  usePagedList: () => ({
    items: [], total: 0, loading: false, page: 1, pageSize: 20,
    hasMore: false, prev: () => {}, next: () => {}, setPageSize: () => {}, refresh: () => {}, fetchAll: async () => [],
  }),
}));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
// recharts butuh ukuran DOM nyata; isi grafik di luar cakupan uji ini.
jest.mock("recharts", () => {
  const Pass = ({ children }) => <div>{children}</div>;
  const Nil = () => null;
  return { ResponsiveContainer: Pass, BarChart: Pass, LineChart: Pass, Bar: Pass, Line: Nil, Cell: Nil,
    XAxis: Nil, YAxis: Nil, CartesianGrid: Nil, Tooltip: Nil };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
let mounted = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  mounted.push({ host, root });
  return { host, root };
}
async function click(el) { await act(async () => { el.click(); }); await act(async () => {}); }
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const key = Object.keys(map).find((k) => url.includes(k));
    return Promise.resolve({ data: key ? map[key] : [] });
  });
}
afterEach(async () => {
  for (const m of mounted) { await act(async () => { m.root.unmount(); }); m.host.remove(); }
  mounted = [];
  mockGet.mockReset(); mockPost.mockReset(); askReason.mockReset();
});

// ── D-17 ────────────────────────────────────────────────────────────────────
test("D-17: satu kontrol status — tab tahap ber-nilai Rp, tanpa kartu pipeline, Sub-status hanya status tahap aktif", async () => {
  routeGet({ "/sales-orders/stats/summary": { total_orders: 3, by_status: {
    reserved: { count: 2, grand_total: 200000 }, waiting_approval: { count: 1, grand_total: 100000 } } } });
  const { host } = await mount(<OrdersView orders={[]} user={{ role: "admin", permissions: {} }} />);
  expect(q(host, "orders-pipeline")).toBeNull();
  expect(q(host, "tab-dashboard").getAttribute("role")).toBe("tab");
  expect(q(host, "tab-list").getAttribute("aria-selected")).toBe("true");
  expect(q(host, "orders-stat-dipesan").textContent).toContain("300.000");
  expect(q(host, "orders-status-detail")).toBeNull();                 // tab "Semua" tidak punya sub-status
  await click(q(host, "orders-status-tab-reserved"));
  const sub = q(host, "orders-status-detail");
  expect([...sub.options].map((o) => o.value)).toEqual(["", "reserved", "waiting_approval", "approved"]);
  expect(sub.options[2].textContent).toBe("Menunggu Persetujuan (1)");
  await click(q(host, "orders-status-tab-done"));
  expect(q(host, "orders-status-detail")).toBeNull();
});

test("D-17: Dasbor Pesanan memuat corong (sumber daftar Pesanan); kecepatan hanya untuk peran Analitik", async () => {
  routeGet({ "/reports/reservation-funnel": { funnel: [{ status: "reserved", count: 2 }], total_orders: 2, sample_excluded: 1 },
    "/reports/order-velocity": { velocity: [], period_days: 7, total_orders: 0 } });
  const sales = await mount(
    <AppNavProvider role="sales" onNavigateTo={() => {}} onOpenDocument={() => {}}><OrderDashboard orders={[]} /></AppNavProvider>);
  expect(q(sales.host, "order-analytics-funnel-scope").textContent).toContain("1 dikecualikan");
  expect(q(sales.host, "order-analytics-velocity")).toBeNull();
  expect(mockGet.mock.calls.some(([u]) => u.includes("/reports/order-velocity"))).toBe(false);
  expect(q(sales.host, "dashboard-top-customers")).not.toBeNull();     // tur tetap menemukan widget
  const admin = await mount(
    <AppNavProvider role="admin" onNavigateTo={() => {}} onOpenDocument={() => {}}><OrderDashboard orders={[]} /></AppNavProvider>);
  expect(q(admin.host, "order-analytics-velocity")).not.toBeNull();
});

test("D-17: Analitik › Ringkasan tanpa widget pesanan ganda — kartu tautan ke Dasbor Pesanan", async () => {
  routeGet({ "/reports/summary": { orders_today: 1 } });
  const { host } = await mount(
    <AppNavProvider role="manager" onNavigateTo={() => {}} onOpenDocument={() => {}}><ManagerDashboard token="t" selectedEntity="all" /></AppNavProvider>);
  expect(q(host, "manager-dashboard-orders-link-open")).not.toBeNull();
  expect(host.textContent).not.toContain("Corong Status Pesanan");
  expect(host.textContent).not.toContain("Pelanggan Teratas");
  const urls = mockGet.mock.calls.map(([u]) => u);
  expect(urls.some((u) => /reservation-funnel|top-customers|order-velocity/.test(u))).toBe(false);
  expect(host.textContent).toContain("Utilisasi Gudang");
});

// ── D-14 ────────────────────────────────────────────────────────────────────
const ENTS = [{ id: "ent_a", short_name: "Sukacita", status: "active" }, { id: "ent_b", short_name: "Kanda", status: "active" }];

test("D-14: Harga per BU — header 'Semua' → kartu pilih PT (mengganti header), tanpa pemilih lokal", async () => {
  routeGet({});
  const pick = jest.fn();
  const { host } = await mount(
    <EntityScopeProvider selectedEntity="all" entities={ENTS} canSwitch pickEntity={pick}>
      <PricelistView entities={ENTS} selectedEntity="all" currentUser={{ permissions: {} }} />
    </EntityScopeProvider>);
  expect(q(host, "pl-entity-required")).not.toBeNull();
  expect(q(host, "pl-entity-select")).toBeNull();
  expect(mockGet.mock.calls.some(([u]) => u.endsWith("/pricelist"))).toBe(false);
  await click(q(host, "pl-entity-required-pick-ent_b"));
  expect(pick).toHaveBeenCalledWith("ent_b");
});

test("D-14: Harga per BU — PT di header langsung dipakai (tanpa pemilih kedua)", async () => {
  routeGet({ "/pricelist": { rows: [], summary: { products: 0 } } });
  const { host } = await mount(
    <EntityScopeProvider selectedEntity="ent_a" entities={ENTS} canSwitch pickEntity={() => {}}>
      <PricelistView entities={ENTS} selectedEntity="ent_a" currentUser={{ permissions: {} }} />
    </EntityScopeProvider>);
  expect(q(host, "pl-entity-required")).toBeNull();
  expect(q(host, "pl-entity-select")).toBeNull();
  const call = mockGet.mock.calls.find(([u]) => u.endsWith("/pricelist"));
  expect(call[1].params.entity_id).toBe("ent_a");
});

// ── D-24a ───────────────────────────────────────────────────────────────────
test("D-24a: Meja Cutting — 'menunggu dipotong gudang' = ringkasan nomor + tautan; penerimaan tetap di sini", async () => {
  routeGet({
    "/cutting/desk": { queues: [
      { key: "to_cut", label: "Menunggu dipotong gudang", rows: [
        { task_id: "t1", order_id: "o1", order_number: "SOS-1", product_name: "Ceruty" },
        { task_id: "t2", order_id: "o1", order_number: "SOS-1", product_name: "Satin" },
        { task_id: "t3", order_id: "o2", order_number: "SOS-2", product_name: "Rayon" }] },
      { key: "to_receive", label: "Hasil potong — menunggu diterima Admin Cutting", rows: [
        { task_id: "t9", order_id: "o9", order_number: "SOS-9", product_name: "Batik", quantity: 1, unit: "meter", warehouse_id: "w1" }] },
    ], wait_thresholds: { warn_minutes: 60, late_minutes: 120 } },
    "/cutting/locations": [{ id: "w1", name: "Gudang A" }],
  });
  const { host } = await mount(<CuttingDesk canReceive />);
  expect(q(host, "cutting-queue-count-to_cut").textContent).toBe("3");
  expect(q(host, "cutting-to-cut-numbers").textContent).toContain("3 baris potong dari 2 pesanan: SOS-1, SOS-2");
  expect(q(host, "cutting-row-t1")).toBeNull();                            // rincian per baris ada di Cutting gudang
  expect(q(host, "cutting-to-cut-link-readonly")).not.toBeNull();         // peran tanpa akses → baca-saja
  expect(q(host, "cutting-receive-t9")).not.toBeNull();                   // penerimaan Admin Cutting tetap
});

// ── D-07 (Matriks divisi) ───────────────────────────────────────────────────
test("D-07: Matriks divisi — PO Custom diputus lewat dialog bersama; tahap lain lewat pop-up FormModal", async () => {
  routeGet({
    "/approvals/my-queue": { items: [
      { stage: "po_custom", id: "sord7", number: "SORD-7", title: "Kain custom", amount: 2000000, customer_name: "Toko", can_decide: true, view: "special-orders" },
      { stage: "purchase_request", id: "pr1", number: "PR-1", title: "Benang", can_decide: true, view: "purchase-requisitions" },
    ], stages: [{ stage: "po_custom" }, { stage: "purchase_request" }], counts: { po_custom: 1, purchase_request: 1 }, total: 2, actionable: 2 },
    "/approvals/matrix-log": { items: [] },
  });
  askReason.mockResolvedValue("");
  mockPost.mockResolvedValue({ data: { status: "confirmed", chain: {} } });
  const { host } = await mount(<MyApprovalsPanel currentUser={{ role: "manager", permissions: {} }} selectedEntity="all" embedded />);
  expect(q(host, "my-approvals-title").textContent).toBe("Matriks divisi");
  await click(q(host, "my-approvals-approve-sord7"));
  expect(askReason).toHaveBeenCalledWith(expect.objectContaining({ testId: "sord-approve-dialog" }));
  expect(mockPost).toHaveBeenCalledWith("/api/special-orders/sord7/approve", { notes: "" });
  expect(q(host, "my-approvals-msg").textContent).toContain("Pesanan disetujui");
  await click(q(host, "my-approvals-reject-pr1"));
  expect(q(host, "my-approvals-modal").getAttribute("role")).toBe("dialog");
  expect(q(host, "my-approvals-modal-submit").disabled).toBe(true);       // alasan < 5 huruf
});

// ── Untuk P6 (D-24c) — pemilih varian mode UBAH ─────────────────────────────
test("SpecVariantFields mode='edit': memuat pilihan tersimpan tanpa menimpa judul/gramasi/lebar", async () => {
  const tpl = {
    id: "tpl1", name: "Rayon Twill", status: "active", gramasi: 120, lebar: 1.5,
    axes: [{ key: "color", label: "Warna", options: [{ code: "NAVY", label: "Navy", value: "NV" }, { code: "ABUX", label: "Abu", value: "AB" }] }],
    variants: [{ id: "p1", sku: "RT-NAVY", name: "Rayon Twill Navy", variant_options: { color: "NAVY" }, spec_id: "spec1", lifecycle: "rnd" }],
  };
  routeGet({ "/product-templates/tpl1": tpl, "/product-templates": [tpl] });
  const onChange = jest.fn();
  const onInherit = jest.fn();
  const { SpecVariantFields } = require("../catalog/SpecVariantFields");
  const { host } = await mount(<SpecVariantFields mode="edit" onChange={onChange} onInherit={onInherit}
    initial={{ templateId: "tpl1", variantOptions: { color: "NAVY" }, newAxisValues: {}, specId: "spec1" }} />);
  expect(onInherit).not.toHaveBeenCalled();                                 // judul/gramasi/lebar form tidak ditimpa
  const last = onChange.mock.calls[onChange.mock.calls.length - 1][0];
  expect(last).toEqual(expect.objectContaining({ template_id: "tpl1", variant_options: { color: "NAVY" }, invalid: "" }));
  expect(q(host, "spec-axis-color").value).toBe("NAVY");
  expect(q(host, "spec-family-select").disabled).toBe(false);              // induk & varian bisa diubah
  // mengubah sumbu = pilihan pengguna → onInherit boleh dipanggil lagi
  await act(async () => { const s = q(host, "spec-axis-color"); s.value = "ABUX"; s.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(onChange.mock.calls[onChange.mock.calls.length - 1][0].variant_options).toEqual({ color: "ABUX" });
  expect(onInherit).toHaveBeenCalled();
});

// ── Preset lintas paket (permintaan P5) ─────────────────────────────────────
test("P5: tautan Cutting gudang membawa preset {stage:'cut', q}; papan 'Barang ditahan QC' → Inspeksi {hold:true}", async () => {
  routeGet({ "/cutting/desk": { queues: [{ key: "to_cut", label: "Menunggu dipotong gudang",
    rows: [{ task_id: "t1", order_id: "o1", order_number: "SOS-1" }] }] }, "/cutting/locations": [] });
  const toView = jest.fn();
  const { host } = await mount(
    <AppNavProvider role="admin" onNavigateTo={toView} onOpenDocument={() => {}}><CuttingDesk /></AppNavProvider>);
  await click(q(host, "cutting-to-cut-link-open"));
  expect(toView).toHaveBeenCalledWith("wms-cutting", expect.objectContaining({ preset: { stage: "cut", q: "SOS-1" } }));

  const HomeWaitingBoards = require("../home/HomeWaitingBoards").default;
  const toView2 = jest.fn();
  const board = { key: "inspection_hold", view: "inspections", count: 1, rows: [{ id: "ins1", number: "INS-1", days_waiting: 1, action: { label: "Lepas", path: "/x" } }] };
  const m = await mount(
    <AppNavProvider role="manager" onNavigateTo={toView2} onOpenDocument={() => {}}>
      <HomeWaitingBoards boards={[board]} ids={() => ({ testIdBase: "qc", rowTestIdBase: "qc-row" })} />
    </AppNavProvider>);
  expect(q(m.host, "qc").getAttribute("data-board-mode")).toBe("link");
  expect(q(m.host, "qc-row-act-ins1")).toBeNull();
  await click(q(m.host, "qc-goto"));
  expect(toView2).toHaveBeenCalledWith("inspections", expect.objectContaining({ preset: { hold: true } }));
});

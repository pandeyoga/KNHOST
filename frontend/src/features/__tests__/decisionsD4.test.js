// Keputusan pemilik 26 Okt (audit UI tahap 2) — D4 sisa lintas wilayah:
// K-03 di layar Pesanan (kolom & ekspor "Total (termasuk PPN)" + DPP, kartu tahap ber-PPN, Ringkasan Harga detail SO
// & pratinjau verifikasi memakai `taxBreakdownRows`; diskon pratinjau tidak lagi terhitung dua kali),
// K-15 label Jejak Audit `period_close_suspense_override`, K-01 label definisi "Lewat Jatuh Tempo" Performa Saya.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { auditActionInfo, auditActionLabel } from "../../config/auditLabels";
import OrderPreviewCard from "../sales_admin/OrderPreviewCard";
import OrdersView from "../orders/OrdersView";
import { OrderDetailPanel } from "../orders/OrderDetailPanel";
import SalesHome from "../home/SalesHome";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
// Daftar pesanan berhalaman (server) → halaman tetap; ekspor CSV ditangkap dari PaginationBar.
jest.mock("../../hooks/usePagedList", () => ({
  usePagedList: () => ({
    items: global.__d4Orders || [], total: (global.__d4Orders || []).length, loading: false, page: 1, pageSize: 20,
    hasMore: false, prev: () => {}, next: () => {}, setPageSize: () => {}, refresh: () => {}, fetchAll: async () => [],
  }),
}));
jest.mock("../../components/PaginationBar", () => (props) => { global.__d4Export = props.exportConfig; return null; });
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
// Panel anak detail SO yang memuat data sendiri — di luar cakupan uji ini.
jest.mock("../documents/ProcessTimeline", () => () => null);
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../documents/RelatedDocsPanel", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);
jest.mock("../finance/payments/SoPaymentPanel", () => () => null);
jest.mock("../orders/DispatchPaymentGatePanel", () => () => null);
jest.mock("../orders/PodProgressNote", () => () => null);
jest.mock("../orders/SoApprovalsPanel", () => () => null);
jest.mock("../orders/OrderFulfillmentBadges", () => () => null);
jest.mock("../orders/OrderIntercoSupplyPanel", () => () => null);
jest.mock("../orders/OrderTransferLinks", () => () => null);
jest.mock("../orders/RestockPanel", () => () => null);
jest.mock("../finance/amendments/AmendmentTrailPanel", () => () => null);
jest.mock("../orders/OrderFeedbackPanel", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).find((k) => url.includes(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
// "Rp 1.045.000" / "− Rp 155.000" → 1045000 (formatCurrency tanpa desimal).
const rupiah = (txt) => Number(String(txt).replace(/[^\d,]/g, "").replace(",", "."));
const rowValue = (host, id) => rupiah(q(host, id).lastElementChild.textContent);

afterEach(() => {
  mockGet.mockReset();
  document.body.innerHTML = "";
  delete global.__d4Orders; delete global.__d4Export;
});

// SO PPN 12% × DPP nilai lain, bruto 1,2 jt, diskon 155 rb (angka sama dengan uji layanan backend test_decisions_d4).
const SO = {
  id: "so_d4", number: "KSC/SO-D4", customer_name: "Toko Uji D4", status: "reserved", entity_id: "ent_ksc",
  items: [{ product_id: "p1", product_name: "Kain A", sku: "A", quantity: 100, unit: "yard", price: 10000 }],
  total_amount: 1200000, discount_total: 155000, net_subtotal: 1045000, dpp: 957916.67, dpp_nilai_lain: true,
  ppn_rate: 12, ppn_mode: "excluded", ppn_amount: 114950, grand_total: 1159950, is_pkp: true,
  created_at: "2026-10-25T03:00:00Z",
};

test("K-15: Jejak Audit memberi label tembus Suspense (bukan 'Aksi lain')", () => {
  expect(auditActionLabel("period_close_suspense_override")).toBe("Tutup buku menembus blokir Suspense");
  expect(auditActionInfo("period_close_suspense_override").known).toBe(true);
  expect(auditActionLabel("period_closed")).toBe("Periode ditutup");   // baris tutup buku biasa tetap
});

test("K-03: pratinjau verifikasi — Subtotal (bruto) − Diskon = DPP; DPP + PPN = Total (diskon tidak dua kali)", async () => {
  const totals = { gross_subtotal: 1200000, net_subtotal: 1045000, discount_total: 155000, dpp: 957916.67,
    dpp_nilai_lain: true, ppn_mode: "excluded", ppn_amount: 114950, ppn_rate: 12, grand_total: 1159950, is_pkp: true };
  const { host } = await mount(<OrderPreviewCard preview={{ customer_name: "Toko Uji", items: [], totals }} testPrefix="pv" />);
  const labels = [...q(host, "pv-totals").querySelectorAll("span:first-child")].map((s) => s.textContent);
  expect(labels).toEqual(["Subtotal (bruto)", "Diskon", "DPP (harga sebelum PPN)", "DPP nilai lain (11/12)",
    "PPN 12% × DPP nilai lain", "Total (termasuk PPN)"]);
  const gross = rowValue(host, "pv-gross");
  const disc = rowValue(host, "pv-discount");
  const dpp = rowValue(host, "pv-dpp");
  const ppn = rowValue(host, "pv-ppn");
  const total = rupiah(q(host, "pv-grand-total").textContent);
  expect(gross - disc).toBe(dpp);                      // dulu: "Subtotal" 1.045.000 − "Diskon" 155.000 = 890.000 ≠ DPP
  expect(dpp + ppn).toBe(total);
  expect(rowValue(host, "pv-dpp_nl")).toBe(957917);
});

test("K-03: pratinjau — server lama tanpa bruto & pesanan tanpa PPN tetap konsisten", async () => {
  const legacy = { net_subtotal: 900000, discount_total: 100000, ppn_amount: 0, ppn_rate: 0, grand_total: 900000, is_pkp: false };
  const { host } = await mount(<OrderPreviewCard preview={{ items: [], totals: legacy }} testPrefix="lg" />);
  expect(rowValue(host, "lg-gross")).toBe(1000000);    // bruto = net + diskon
  expect(rowValue(host, "lg-net")).toBe(900000);
  expect(q(host, "lg-totals").textContent).toContain("PPN (non-PKP)");
  expect(q(host, "lg-total-label").textContent).toBe("Total Pesanan");
  expect(q(host, "lg-dpp")).toBeNull();
});

test("K-03: daftar Pesanan — kolom 'Total (termasuk PPN)' + DPP; kartu tahap ber-PPN; ekspor CSV", async () => {
  global.__d4Orders = [SO, { ...SO, id: "so_np", number: "KSC/SO-NP", ppn_amount: 0, dpp: 1045000, grand_total: 1045000 }];
  routeGet({ "/sales-orders/stats/summary": { total_orders: 2, by_status: {
    reserved: { count: 2, total_amount: 2400000, grand_total: 2204950 } } } });
  const { host } = await mount(<OrdersView orders={[]} user={{ role: "admin", permissions: {} }} />);
  expect(q(host, "orders-col-total").textContent).toBe("Total (termasuk PPN)");
  expect(q(host, "orders-col-total-dpp")).toBeNull();
  expect(rupiah(q(host, "order-total-so_d4").textContent)).toBe(1159950);   // dulu total_amount bruto 1.200.000
  expect(rupiah(q(host, "order-dpp-so_d4").textContent)).toBe(1045000);
  expect(q(host, "order-dpp-so_np")).toBeNull();                              // tanpa PPN: tidak ada baris DPP
  const card = q(host, "orders-stat-dipesan");
  expect(card.textContent).toContain("2.204.950");                           // grand_total per status, bukan bruto
  expect(card.getAttribute("title")).toMatch(/total termasuk PPN/);
  const cols = global.__d4Export.columns;
  const tot = cols.find((c) => c.header === "Total (termasuk PPN)");
  const dpp = cols.find((c) => c.header === "DPP (harga sebelum PPN)");
  expect(cols.some((c) => c.header === "Total (DPP)")).toBe(false);
  expect(tot.get(SO)).toBe(1159950);
  expect(dpp.get(SO)).toBe(1045000);
});

test("K-03: kartu tahap — server lama tanpa grand_total jatuh ke total_amount", async () => {
  global.__d4Orders = [];
  routeGet({ "/sales-orders/stats/summary": { total_orders: 1, by_status: { done: { count: 1, total_amount: 500000 } } } });
  const { host } = await mount(<OrdersView orders={[]} user={{ role: "admin", permissions: {} }} />);
  expect(q(host, "orders-stat-selesai").textContent).toContain("500.000");
});

test("K-03: Ringkasan Harga detail SO = DPP · DPP nilai lain (11/12) · PPN · Total (termasuk PPN)", async () => {
  routeGet({});
  const { host } = await mount(<OrderDetailPanel order={SO} user={{ role: "admin", permissions: {} }} embedded />);
  const box = q(host, "order-pricing-breakdown");
  expect(box.textContent).not.toContain("Subtotal netto (DPP)");
  expect(box.textContent).not.toContain("Grand Total");
  expect(q(host, "order-grand-total-label").textContent.trim()).toBe("Total (termasuk PPN)");
  const val = (k) => rupiah(q(host, `order-break-${k}`).querySelector("div").lastElementChild.textContent);
  expect(q(host, "order-break-dpp").textContent).toContain("DPP (harga sebelum PPN)");
  expect(q(host, "order-break-dpp_nl").textContent).toContain("DPP nilai lain (11/12)");
  expect(q(host, "order-break-ppn").textContent).toContain("PPN 12% × DPP nilai lain");
  expect(val("dpp") + val("ppn")).toBe(rupiah(q(host, "order-grand-total").textContent));
  expect(1200000 - 155000).toBe(val("dpp"));           // Subtotal (bruto) − Diskon = DPP
});

test("K-03: detail SO tanpa PPN — label lama tetap (Subtotal netto (DPP) · Grand Total)", async () => {
  routeGet({});
  const np = { ...SO, ppn_amount: 0, ppn_rate: 0, dpp: 1045000, grand_total: 1045000, is_pkp: false };
  const { host } = await mount(<OrderDetailPanel order={np} user={{ role: "admin", permissions: {} }} embedded />);
  const box = q(host, "order-pricing-breakdown");
  expect(box.textContent).toContain("Subtotal netto (DPP)");
  expect(box.textContent).toContain("Non-PKP (0)");
  expect(q(host, "order-grand-total-label").textContent.trim()).toBe("Grand Total");
  expect(q(host, "order-break-dpp")).toBeNull();
});

test("K-01: Performa Saya — 'Lewat Jatuh Tempo' menyebut definisi layar Piutang", async () => {
  routeGet({ "/home/sales": { period: "2026-10", commission: {}, target: {}, kpi: { overdue_amount: 700000 },
    history: [], customers: [], collections: [], recent_orders: [], waiting_boards: [] } });
  const { host } = await mount(<SalesHome user={{ id: "u1", role: "sales", name: "Sales" }} />);
  expect(host.textContent).toContain("Pelanggan saya · lewat ≥ 1 hari, sama dengan layar Piutang");
});

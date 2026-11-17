// Latihan Keuangan 17 Nov (F05) — tautan "Buka pesanan" tanpa nomor (Rencana & Denda, Titipan & Saldo Kredit, Inbox
// Persetujuan): Daftar Pesanan mengambil nomornya dan menyaring ke pesanan itu, supaya panelnya terbuka walau di luar hal. 1.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import OrdersView from "../orders/OrdersView";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
let mockPagedItems = [];
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    isCancel: () => false, defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../hooks/usePagedList", () => ({
  usePagedList: () => ({
    items: mockPagedItems, total: mockPagedItems.length, loading: false, page: 1, pageSize: 20,
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
jest.mock("../designer/DivisionsView", () => () => null);

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
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    return Promise.resolve({ data: key ? map[key] : [] });
  });
}
afterEach(async () => {
  for (const m of mounted) { await act(async () => { m.root.unmount(); }); m.host.remove(); }
  mounted = [];
  mockGet.mockReset();
  mockPagedItems = [];
  setAccessContext(null);
  jest.restoreAllMocks();
});

test("focus tanpa nomor → nomor diambil dari server → kotak cari = nomor tepat", async () => {
  routeGet({ "/sales-orders/so_latih_x": { id: "so_latih_x", number: "KSC/SO-00006" } });
  const focus = { focus_type: "sales_order", focus_id: "so_latih_x" };
  const { host } = await mount(<OrdersView orders={[]} user={{ role: "admin", permissions: {} }} focusDoc={focus} onClearFocus={() => {}} />);
  await act(async () => {});
  expect(mockGet.mock.calls.some(([u]) => String(u).includes("/sales-orders/so_latih_x"))).toBe(true);
  expect(q(host, "orders-search-input").value).toBe('"KSC/SO-00006"');
});

test("focus dengan nomor → tidak perlu bertanya ke server", async () => {
  routeGet({});
  const focus = { focus_type: "sales_order", focus_id: "so_latih_y", number: "KSC/SO-00007" };
  const { host } = await mount(<OrdersView orders={[]} user={{ role: "admin", permissions: {} }} focusDoc={focus} onClearFocus={() => {}} />);
  expect(mockGet.mock.calls.some(([u]) => String(u).includes("/sales-orders/so_latih_y"))).toBe(false);
  expect(q(host, "orders-search-input").value).toBe('"KSC/SO-00007"');
});

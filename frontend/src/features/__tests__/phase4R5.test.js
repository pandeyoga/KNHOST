// Fase 4 · R5 — antrean persetujuan (Pusat Persetujuan), Backorder = status Menunggu stok (keputusan pemilik #2),
// dan panggilan latar `/config/health` hanya untuk pemegang `settings.view`.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { loadInbox } from "../approvals/approvalInboxData";
import { BACKLOG_INBOX_TAB, LISTED_IN_INBOX, SO_DEAD_STATUSES, queueLink } from "../approvals/inboxTabs";
import { hasPartialBackorder, isBackorderSo } from "../orders/soStatusView";
import OrdersView from "../orders/OrdersView";
import SettingsGroupView from "../settings/cfg/SettingsGroupView";
import { configApi } from "../settings/config/configApi";
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

test("R5 Pusat Persetujuan: entri SO mati & override tertaut SO tidak tampil; override mandiri = antrean credit_override", async () => {
  routeGet({
    "/approvals/queue": [
      { id: "a1", type: "kredit", order_id: "so1", order_number: "KANDA/SO-00001", order_status: "expired", requested_at: "2026-10-20T01:00:00Z", ref_id: "cro1" },
      { id: "a3", type: "nilai", order_id: "so3", order_number: "KSC/SOS-00013", order_status: "cancelled", requested_at: "2026-10-20T02:00:00Z" },
      { id: "a2", type: "nilai", order_id: "so2", order_number: "KSC/SO-00002", order_status: "reserved", requested_at: "2026-10-21T01:00:00Z" },
    ],
    "/credit-overrides": [
      { id: "cro1", customer_name: "CV Garmen", order_id: "so1", order_number: "KANDA/SO-00001", status: "pending", created_at: "2026-10-20T01:00:00Z" },
      { id: "cro2", customer_name: "Toko B", order_id: "", status: "pending", created_at: "2026-10-22T01:00:00Z" },
    ],
    "/approvals/backlog": { total: 2, items: [], all_items: [{ key: "sales_order", count: 1 }, { key: "credit_override", count: 1 }] },
  });
  const res = await loadInbox();
  expect(res.items.map((i) => i.id)).toEqual(["a2", "cro2"]);
  expect(res.items.find((i) => i.id === "cro2").kind).toBe("credit");
  expect(SO_DEAD_STATUSES).toEqual(expect.arrayContaining(["cancelled", "expired"]));
  // Antrean server baru `credit_override` = daftar tab Kredit (bukan "ditangani di layar lain").
  expect(LISTED_IN_INBOX).toContain("credit_override");
  expect(BACKLOG_INBOX_TAB.credit_override).toBe("credit");
  expect(queueLink({ key: "credit_override", view: "approval-inbox" }, () => true)).toEqual({ view: "approval-inbox", preset: { tab: "credit" } });
  expect(queueLink({ key: "od_cancel_credit_note", view: "finance-desk" }, () => true)).toEqual({ view: "finance-desk" });
});

test("R5 Backorder = status Menunggu stok; sisa pendingan SO hidup = 'Sebagian menunggu stok'; SO batal tanpa penanda", async () => {
  expect(isBackorderSo({ status: "waiting_stock" })).toBe(true);
  expect(isBackorderSo({ status: "reserved", has_backorder: true })).toBe(false);
  expect(hasPartialBackorder({ status: "reserved", has_backorder: true })).toBe(true);
  expect(hasPartialBackorder({ status: "cancelled", has_backorder: true })).toBe(false);   // penanda basi
  expect(hasPartialBackorder({ status: "waiting_stock", has_backorder: true })).toBe(false);

  mockPagedItems = [
    { id: "bo", number: "KSC/SO-1", status: "waiting_stock", has_backorder: true, customer_name: "A", items: [] },
    { id: "pt", number: "KSC/SO-2", status: "reserved", has_backorder: true, customer_name: "B", items: [] },
    { id: "cx", number: "KSC/SO-3", status: "cancelled", has_backorder: true, customer_name: "C", items: [] },
  ];
  routeGet({ "/sales-orders/stats/summary": { total_orders: 3, backorder_count: 1, partial_backorder_count: 1,
    by_status: { waiting_stock: { count: 1, grand_total: 1 }, reserved: { count: 1, grand_total: 1 }, cancelled: { count: 1, grand_total: 1 } } } });
  const { host } = await mount(<OrdersView orders={[]} user={{ role: "admin", permissions: {} }} />);
  expect(q(host, "order-backorder-chip-bo")).not.toBeNull();
  expect(q(host, "order-backorder-chip-pt")).toBeNull();
  expect(q(host, "order-partial-stock-chip-pt").textContent).toBe("Sebagian menunggu stok");
  expect(q(host, "order-backorder-chip-cx")).toBeNull();
  expect(q(host, "order-partial-stock-chip-cx")).toBeNull();
  expect(q(host, "orders-status-tab-waiting_stock").getAttribute("title")).toContain("1 SO lain (tahap lain) sebagian masih menunggu stok");
});

describe("R5 Pengaturan: /config/health hanya untuk pemegang settings.view", () => {
  const groups = [{ id: "retur", label: "Retur Penjualan", question: "?", count: 1 }];
  const items = [{ key: "returns.photo_required", group: "retur", label: "Foto retur", value: true, default: true, type: "bool",
    status: "active", scopes: ["global"], help: "", impact: "", example: "", source_layer: "code_default", source_label: "Bawaan", can_edit: false }];
  function spies() {
    jest.spyOn(configApi, "registry").mockResolvedValue({ groups, entries: items, caps: { settings_manage: false } });
    jest.spyOn(configApi, "effective").mockResolvedValue({ items });
    return jest.spyOn(configApi, "health").mockResolvedValue({ rows: [] });
  }

  test("Admin Sales (tanpa settings.view) — tidak menembak /config/health; kartu tetap tampil", async () => {
    const health = spies();
    setAccessContext({ role: "sales_admin", permissions: { order: ["view"] }, view_resources: {}, hidden_views: [] });
    const { host } = await mount(<SettingsGroupView view="settings-cfg-sales" currentUser={{ role: "sales_admin", permissions: { order: ["view"] } }} entities={[]} />);
    expect(health).not.toHaveBeenCalled();
    expect(q(host, "cfg-card-wrap-returns.photo_required")).not.toBeNull();
  });

  test("Manajer (settings.view) — peta kesehatan tetap dimuat", async () => {
    const health = spies();
    setAccessContext({ role: "manager", permissions: { settings: ["view"] }, view_resources: {}, hidden_views: [] });
    await mount(<SettingsGroupView view="settings-cfg-sales" currentUser={{ role: "manager", permissions: { settings: ["view"] } }} entities={[]} />);
    expect(health).toHaveBeenCalled();
  });
});

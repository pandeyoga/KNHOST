// UAT 24 Okt — fase F4: P15 gabung PR → 1 PO (syarat PR bisa digabung) · P2 harga Pesanan Khusus (dasar harga,
// biaya tersembunyi untuk sales, kunci hanya pemegang od_pricing.lock, nego per baris SO).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { canMerge } from "../purchasing/PrMergePanel";
import SpecialOrderPricingPanel from "../sales/SpecialOrderPricingPanel";

const PRICING = {
  mode: "items", locked: true, locked_by: "Admin Sales", locked_at: "2026-10-24T03:00:00Z", total: 1860000,
  items: [
    { item_id: "soi_1", line_no: 1, description: "Kain induk", product_sku: "OD-1", quantity: 100, unit: "yard", basis: "parent_grade_a",
      basis_label: "Harga Grade A induk", ref_sku: "KNWVN0012-L-4XXX-XA-XX-XX", price_per_unit: 13000, final_unit_price: 13000, total: 1300000 },
    { item_id: "soi_2", line_no: 2, description: "Kain referensi", product_sku: "OD-2", quantity: 40, unit: "yard", basis: "pic",
      basis_label: "Harga PIC Special Order", price_per_unit: 14000, final_unit_price: 14000, total: 560000 },
  ],
  nego: { so_id: "so_1", so_number: "KSC/SO-00099", so_status: "waiting_stock", block: "",
    entries: [{ id: "e1", status: "rejected", requested_price: 12000, requested_by: "Sales", special_order_item_id: "soi_2", product_id: "p2" }],
    lines: [{ index: 0, special_order_item_id: "soi_1", product_id: "p1", product_name: "OD-1", quantity: 100, unit: "yard", price: 13000 },
      { index: 1, special_order_item_id: "soi_2", product_id: "p2", product_name: "OD-2", quantity: 40, unit: "yard", price: 14000 }] },
};

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: () => Promise.resolve({ data: PRICING }), post: jest.fn() }, API: "/api" }));
jest.mock("../../components/SiteSelect", () => () => null);
jest.mock("@/services/confirmService", () => ({ askReason: jest.fn() }));
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn() }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("P15 — PR bisa digabung bila approved/converted dan masih ada baris pembelian terbuka", () => {
  const line = { product_id: "p1", quantity: 10, realized_qty: 0, fulfillment_mode: "purchase" };
  expect(canMerge({ status: "approved", items: [line] })).toBe(true);
  expect(canMerge({ status: "converted", items: [{ ...line, realized_qty: 4 }] })).toBe(true);
  expect(canMerge({ status: "draft", items: [line] })).toBe(false);
  expect(canMerge({ status: "approved", items: [{ ...line, realized_qty: 10 }] })).toBe(false);
  expect(canMerge({ status: "approved", items: [{ ...line, fulfillment_mode: "makloon" }] })).toBe(false);
});

test("P2 — sales melihat harga final & dasar harga, tanpa kolom biaya / tombol kunci; nego per baris & lanjut harga normal", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const sales = { role: "sales", permissions: { order: ["view", "update"] } };
  const order = { id: "sord_1", number: "SORD-1", status: "confirmed", customer_decision: "acc", chain: { pricing: PRICING, po: [] } };
  await act(async () => { root.render(<SpecialOrderPricingPanel order={order} currentUser={sales} />); });
  await act(async () => { await new Promise((r) => setTimeout(r, 300)); });
  const text = host.textContent;
  expect(text).toContain("Harga Grade A induk");
  expect(text).toContain("Harga PIC Special Order");
  expect(text).not.toMatch(/Kontrak · pembanding/);
  expect(host.querySelector('[data-testid="od-price-lock-button"]')).toBeNull();
  expect(host.querySelector('[data-testid="od-nego-open-0"]')).not.toBeNull();
  expect(host.querySelector('[data-testid="od-nego-normal-1"]')).not.toBeNull();   // nego item 2 ditolak → lanjut harga normal
  act(() => root.unmount());
});

test("P2 — Admin Sales (od_pricing.lock + view_cost) melihat kolom kontrak & tombol kunci sebelum harga dikunci", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const sadm = { role: "sales_admin", permissions: { order: ["view", "update"], od_pricing: ["lock", "set_price", "view_cost"] } };
  const open = { ...PRICING, locked: false, ready: true,
    items: PRICING.items.map((it) => ({ ...it, ready: true, cost_price: 10000, comparator_unit_price: 13000, basis: it.line_no === 2 ? "cost_margin" : it.basis })) };
  const order = { id: "sord_2", number: "SORD-2", status: "confirmed", customer_decision: "acc", chain: { pricing: open, po: [] } };
  const api = require("../../services/apiClient").default;
  api.get = () => Promise.resolve({ data: open });
  await act(async () => { root.render(<SpecialOrderPricingPanel order={order} currentUser={sadm} />); });
  await act(async () => { await new Promise((r) => setTimeout(r, 300)); });
  expect(host.textContent).toMatch(/Kontrak · pembanding/);
  expect(host.querySelector('[data-testid="od-price-lock-button"]').textContent).toMatch(/Kunci harga & buat SO/);
  expect(host.querySelector('[data-testid="od-price-item-pic-2"]')).not.toBeNull();     // item tanpa induk: isian PIC
  expect(host.querySelector('[data-testid="od-price-item-pic-1"]')).toBeNull();         // item ber-induk: Grade A
  act(() => root.unmount());
});

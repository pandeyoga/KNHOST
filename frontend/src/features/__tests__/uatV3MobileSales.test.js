// Cek UI UAT v3 (2026-10-22) — aplikasi HP Sales (UAT peran Sales memakai tampilan mobile):
// menu Lainnya dulu kosong (Retur, Pesanan Sample, Pesanan Khusus, Minta Harga Khusus … tersaring), detail pesanan HP
// tidak punya jalur harga khusus per SO / persetujuan kredit, daftar retur menulis Rp 0, catatan pemutus tak terlihat.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import MobileMore from "../sales/mobile/MobileMore";
import MobileOrders from "../sales/mobile/MobileOrders";
import { returnValueText } from "../sales/mobile/MobileSalesNative";
import SoApprovalsPanel from "../orders/SoApprovalsPanel";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: jest.fn(async () => ({ data: [] })), post: jest.fn(), defaults: { headers: { common: {} } } }, API: "/api" }));
jest.mock("../sales/mobile/MobileOrderJourney", () => () => null);
jest.mock("../sales/mobile/MobilePendingQueue", () => () => null);
jest.mock("../tanya/TanyaKnView", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  return { host, root };
}
const SALES = { role: "sales", name: "Ayu", email: "sales@x", permissions: { order: ["view", "create"], price_approval: ["create"] } };

test("menu Lainnya HP sales menampilkan Retur, Pesanan Sample, Pesanan Khusus, Minta Harga Khusus", async () => {
  try { localStorage.clear(); } catch { /* abaikan */ }
  const { host, root } = await mount(<MobileMore user={SALES} sub={null} setSub={() => {}} entities={[]} />);
  for (const id of ["returns", "sample-orders", "special", "special-price", "price-status", "crm", "stock"]) {
    expect(q(host, `mobile-more-${id}`)).not.toBeNull();            // dulu: semua tersaring (tidak punya `nav`)
  }
  expect(q(host, "mobile-more-approvals")).toBeNull();               // khusus Admin Sales
  await act(async () => { root.unmount(); });
});

test("detail pesanan HP: panel persetujuan + [Ajukan Harga Khusus] untuk SO terbuka", async () => {
  const order = { id: "so1", number: "KSC/SO-1", status: "reserved", customer_id: "c1", customer_name: "Toko", payment_status: "unpaid",
    items: [{ product_id: "p1", product_name: "Ceruty", quantity: 50, price: 20000 }], pending_approvals: [] };
  const { host, root } = await mount(<MobileOrders orders={[order]} role="sales" user={SALES} focusId="so1" />);
  expect(q(host, "mobile-order-approvals-so1")).not.toBeNull();
  expect(q(host, "so-appr-request-sp-toggle")).not.toBeNull();       // dulu: tidak ada di HP
  await act(async () => { root.unmount(); });
});

test("entri ditolak menampilkan catatan pemutus", async () => {
  const order = { id: "so1", status: "reserved", items: [], pending_approvals: [
    { id: "a1", type: "special_price", status: "rejected", reason: "Nego", requested_by: "Ayu", required_role: "manager",
      decided_by: "Dewi", decision_notes: "Margin terlalu tipis", product_name: "Ceruty", normal_price: 20000, requested_price: 17500 }] };
  const { host, root } = await mount(<SoApprovalsPanel order={order} user={SALES} />);
  expect(q(host, "so-appr-decision-notes-a1").textContent).toMatch(/Margin terlalu tipis/);
  await act(async () => { root.unmount(); });
});

test("daftar retur HP: tanpa nilai rupiah tampil qty klaim, bukan Rp 0", () => {
  expect(returnValueText({ items: [{ quantity_returned: 2, unit: "yard" }, { quantity_returned: 1.5, unit: "kg" }] })).toMatch(/klaim 2 yard · 1,5 kg/);
  expect(returnValueText({ total_amount: 50000, items: [] })).toMatch(/50\.000/);
  expect(returnValueText({ items: [] })).toBe("—");
});

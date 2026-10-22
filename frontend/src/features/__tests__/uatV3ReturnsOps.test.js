// Cek UI UAT v3 (2026-10-22) — celah antarmuka dari skenario S10–S16 (retur, sample, transit, pembelian):
// tautan giliran "approvals" punya layar; roll kg tidak ditampilkan sebagai meter/yard; retur Penggantian
// diselesaikan sebagai Store Credit dengan petunjuk; Finance melihat harga transaksi & nominal diskon disarankan;
// kartu HP sample gratis "Gratis" tanpa tombol bayar; label status tugas gudang berbahasa Indonesia.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { resolveView } from "../../utils/viewAlias";
import { dualLen } from "../../components/RollPicker";
import ReturnSettleModal from "../sales/ReturnSettleModal";
import ReturnCompensationPanel from "../sales/ReturnCompensationPanel";
import MobileOrders from "../sales/mobile/MobileOrders";
import { Badge } from "../wms/OutboundScanBadges";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() }, API: "/api" }));
jest.mock("../../config/roles", () => ({ ...jest.requireActual("../../config/roles"), canCurrent: () => true, roleIs: () => false }));
jest.mock("../sales/CutlossSplitPanel", () => () => null);
jest.mock("../sales/mobile/MobilePendingQueue", () => () => null);
jest.mock("../sales/mobile/MobileOrderJourney", () => () => null);
jest.mock("../orders/SoApprovalsPanel", () => () => null);
const axios = require("../../services/apiClient").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await tick();
  return { host, root };
}
beforeEach(() => { axios.get.mockReset(); axios.post.mockReset(); axios.get.mockResolvedValue({ data: [] }); });

test("tautan giliran/notifikasi lama dipetakan ke layar yang dirender", () => {
  expect(resolveView("approvals")).toBe("approval-inbox");          // dulu halaman kosong
  expect(resolveView("finance")).toBe("finance-desk");
  expect(resolveView("purchase-orders")).toBe("purchasing");
  expect(resolveView("returns")).toBe("returns");
  expect(resolveView(undefined)).toBeUndefined();
});

test("roll kg ditampilkan dalam kg, bukan meter ≈ yard", () => {
  expect(dualLen(20.37, "kg")).toBe("20,37 kg");
  expect(dualLen(100, "yard")).toMatch(/m ≈ 100 yd$/);
});

test("retur Penggantian: default Store Credit + petunjuk pesanan pengganti, label bahasa Indonesia", async () => {
  const ret = { id: "sret_1", number: "SRET-1", return_type: "penggantian", items: [{ quantity_returned: 42.2 }], roll_locations: {} };
  const { host } = await mount(<ReturnSettleModal ret={ret} open onClose={() => {}} onSettle={async () => null} />);
  expect(q(host, "settle-swap-hint").textContent).toMatch(/Store Credit/);
  expect(q(host, "confirm-settle-btn").textContent).toMatch(/Selesaikan \(Store Credit\)/);   // dulu "(store_credit)"
  await act(async () => { q(host, "settle-outcome-refund").click(); });
  expect(q(host, "settle-swap-hint").textContent).toMatch(/tidak bisa dibuatkan pesanan pengganti/);
});

test("kompensasi: harga transaksi tampil & nominal diskon disarankan, berhenti mengikuti setelah diketik", async () => {
  axios.get.mockResolvedValue({ data: { cutloss: [], compensation: {}, basis: "Harga transaksi awal × qty cacat" } });
  const ret = { id: "sret_2", status: "inspected", items: [{ product_id: "p1", product_name: "Ceruty", unit: "yard", unit_price_est: 20000 }] };
  const { host } = await mount(<ReturnCompensationPanel ret={ret} canApprove onChanged={() => {}} />);
  expect(q(host, "discount-price-p1").textContent).toMatch(/Rp\s20\.000\/yard/);   // formatCurrency memakai spasi tak-putus
  const setVal = async (el, v) => act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await setVal(q(host, "discount-qty-p1"), "2");
  expect(q(host, "discount-amount-p1").value).toBe("40000");
  await setVal(q(host, "discount-amount-p1"), "35000");
  await setVal(q(host, "discount-qty-p1"), "3");
  expect(q(host, "discount-amount-p1").value).toBe("35000");                 // nominal manual tidak ditimpa
});

test("kartu HP: sample gratis tertulis Gratis tanpa tombol Catat bayar", async () => {
  const o = { id: "so_s1", number: "KSC/SOS-1", status: "approved", order_type: "sample", sample_billing: "free",
    grand_total: 0, payment_status: "unpaid", customer_name: "Toko", items: [{}] };
  const { host } = await mount(<MobileOrders orders={[o]} role="sales" user={{ role: "sales" }} />);
  expect(q(host, "mobile-order-so_s1").textContent).toMatch(/Gratis/);
  await act(async () => { q(host, "mobile-order-so_s1").querySelector("button").click(); });
  expect(q(host, "mobile-order-pay-so_s1")).toBeNull();
});

test("label status tugas Barang Keluar berbahasa Indonesia", async () => {
  const { host } = await mount(<div><Badge status="created" /><Badge status="escalated" /></div>);
  expect(host.textContent).toBe("Siap diambilDieskalasi");
});

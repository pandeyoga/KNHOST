// Cek UI UAT v3 (2026-10-21) — celah antarmuka dari skenario S2 (termin CBD, bayar sebelum kirim):
// Review checkout memberi tahu barang ditahan sampai dibayar; Barang Keluar tidak kehilangan nama pelanggan &
// status "Tertahan bayar" setelah [Kirim Pengambilan]; tombol "Catat pembayaran" di detail SO membuka kwitansi dengan
// pesanan itu di urutan teratas; kartu antrean bisa dicari; label tahap SO berbahasa Indonesia.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CheckoutStep3 from "../pos/CheckoutStep3";
import DeskQueueCard from "../sales_admin/DeskQueueCard";
import DispatchPaymentGatePanel from "../orders/DispatchPaymentGatePanel";
import OutboundScanInterface from "../wms/OutboundScanInterface";
import { stageMeta } from "../../utils/soStatus";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() }, API: "/api" }));
jest.mock("../finance/payments/paymentApi", () => ({
  varianceMeta: jest.fn(async () => ({ reasons: [] })), assessVariance: jest.fn(async () => null), directionMeta: () => ({}) }));
jest.mock("../finance/payments/PaymentVarianceDialog", () => () => null);
jest.mock("@/components/KNDatePicker", () => () => null);
jest.mock("../wms/LoadingCheckPanel", () => () => null);
jest.mock("../wms/SampleCutPanel", () => () => null);
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn() }));
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
beforeEach(() => { axios.get.mockReset(); axios.post.mockReset(); });

const HOLD = { applies: true, blocked: true, term_code: "CBD", term_name: "CBD — Bayar Sebelum Kirim", dp_percent: 100,
  grand_total: 782994, required: 782994, paid: 0, shortfall: 782994, released: null, mode: "block" };

test("review checkout: termin CBD/DP memberi tahu pengiriman tertahan sampai dibayar", async () => {
  const props = { fulfillmentMethod: "kirim", setFulfillmentMethod: () => {}, pickupDate: "", setPickupDate: () => {},
    deliveryDate: "", setDeliveryDate: () => {}, selectedCustomer: { name: "Toko" }, addresses: [], selectedAddress: "",
    p: { gross: 699102, ppn: 0, grand: 782994, isPkp: false }, cart: [], pricedCart: [], paymentTerm: "CBD",
    needsTaxInvoice: false, setNeedsTaxInvoice: () => {}, credit: null };
  const cbd = await mount(<CheckoutStep3 {...props} termInfo={{ code: "CBD", name: "CBD — Bayar Sebelum Kirim", dp_percent: 100 }} />);
  expect(q(cbd.host, "checkout-pay-before-dispatch").textContent).toMatch(/wajib dibayar 100% \(Rp\s?782\.994\) sebelum kirim/);
  const net = await mount(<CheckoutStep3 {...props} paymentTerm="NET30" termInfo={{ code: "NET30", dp_percent: 0 }} />);
  expect(q(net.host, "checkout-pay-before-dispatch")).toBeNull();
  const sample = await mount(<CheckoutStep3 {...props} sampleMode termInfo={{ code: "CBD", dp_percent: 100 }} />);
  expect(q(sample.host, "checkout-pay-before-dispatch")).toBeNull();     // sample punya gerbang bayarnya sendiri
  for (const m of [cbd, net, sample]) await act(async () => { m.root.unmount(); });
});

test("Barang Keluar: setelah [Kirim Pengambilan] nama pelanggan & status Tertahan bayar tetap tampil", async () => {
  const TASK = { id: "t1", order_id: "so1", order_number: "KSC/SO-1", status: "created", product_id: "p1", sku: "SKU1",
    product_name: "Ceruty", warehouse_id: "wh1", warehouse_name: "Gudang", quantity: 10, picked_qty: 0, shipped_qty: 0,
    unit: "yard", customer_name: "Toko Kain Sejahtera", payment_hold: HOLD };
  axios.get.mockImplementation(async (url) => {
    if (url === "/api/outbound/tasks") return { data: [TASK] };
    if (url === "/api/outbound/tasks/t1/pick-list") return { data: { unit: "yard", pending_cuts: [],
      rolls: [{ id: "r1", roll_no: "RL-1", length_remaining: 10, picked: false }] } };
    if (url === "/api/inventory/rolls") return { data: [{ id: "r1", roll_no: "RL-1", warehouse_id: "wh1", status: "reserved",
      reserved_ref: { id: "so1" }, length_remaining: 10 }] };
    return { data: {} };
  });
  // respons scan-pick = tugas MENTAH (tanpa pengayaan daftar: nama pelanggan, status bayar)
  axios.post.mockResolvedValue({ data: { id: "t1", order_id: "so1", order_number: "KSC/SO-1", status: "packing",
    quantity: 10, picked_qty: 10, shipped_qty: 0, unit: "yard", warehouse_id: "wh1" } });
  const { host, root } = await mount(<OutboundScanInterface user={{ permissions: {} }} />);
  await act(async () => { q(host, "outbound-task-t1").click(); });
  await tick();
  expect(host.textContent).toMatch(/Customer: Toko Kain Sejahtera/);
  await act(async () => { q(host, "outbound-pick-take-RL-1").click(); });
  await tick();
  await act(async () => { q(host, "scan-task-t1").click(); });
  await tick();
  expect(axios.post).toHaveBeenCalledWith("/api/outbound/tasks/t1/scan-pick", null, expect.anything());
  expect(host.textContent).toMatch(/Customer: Toko Kain Sejahtera/);                        // dulu: "Customer:" kosong
  expect(q(host, "outbound-gate-summary").textContent).toMatch(/Tertahan/);                 // dulu: panel hilang
  expect([...host.querySelectorAll("button")].find((b) => /Kirim Semua/.test(b.textContent)).disabled).toBe(true);
  await act(async () => { root.unmount(); });
});

test("detail SO tertahan: [Catat pembayaran] membuka kwitansi dengan SO itu di urutan teratas & terisi", async () => {
  axios.get.mockImplementation(async (url) => {
    if (url === "/api/ar-receipts/open-orders") return { data: [
      { order_id: "lama", number: "KSC/SO-0001", outstanding: 50000 },
      { order_id: "so1", number: "KSC/SO-0346", outstanding: 782994 }] };
    return { data: {} };
  });
  const fin = { permissions: { ar_receipt: ["create"], order: ["view"] } };
  const { host, root } = await mount(<DispatchPaymentGatePanel orderId="so1" initial={HOLD} currentUser={fin}
                                                               customerId="c1" customerName="Toko" />);
  expect(q(host, "so-gate-release-open")).toBeNull();                       // tanpa izin release_unpaid
  await act(async () => { q(host, "so-gate-receipt-open").click(); });
  await tick();
  expect(axios.get).toHaveBeenCalledWith("/api/ar-receipts/open-orders", { params: { customer_id: "c1" } });
  const rows = [...document.querySelectorAll('[data-testid^="ar-receipt-order-"]')].map((e) => e.getAttribute("data-testid"));
  expect(rows[0]).toBe("ar-receipt-order-so1");                             // dulu: terselip di urutan ke-N
  expect(document.querySelector('[data-testid="ar-receipt-alloc-so1"]').value).toMatch(/^782.?994$/);
  await act(async () => { root.unmount(); });

  // tanpa izin catat kwitansi → tombol tidak tampil
  const sales = await mount(<DispatchPaymentGatePanel orderId="so1" initial={HOLD} currentUser={{ permissions: {} }} customerId="c1" />);
  expect(q(sales.host, "so-gate-receipt-open")).toBeNull();
  await act(async () => { sales.root.unmount(); });
});

test("kartu antrean: kolom cari menyaring nomor/pelanggan; testid baris memakai row_key (beberapa SO per pelanggan)", async () => {
  const rows = Array.from({ length: 7 }, (_, i) => ({ ref_type: "customer", ref_id: "cust1", row_key: `so${i}`,
    number: `KSC/SO-00${340 + i}`, title: "Toko Kain Sejahtera", value: 1000 * (i + 1), age_days: 7 - i }));
  const queue = { id: "bayar_sebelum_kirim", label: "Menunggu pembayaran", value_kind: "money", count: 7, rows };
  const { host, root } = await mount(<DeskQueueCard queue={queue} testPrefix="fin-desk" rowTestPrefix="fin-desk-bsk" defaultOpen />);
  expect(q(host, "fin-desk-bsk-row-so6")).toBeNull();                       // halaman 2
  const input = q(host, "fin-desk-search-bayar_sebelum_kirim");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "SO-00346");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(q(host, "fin-desk-bsk-row-so6")).not.toBeNull();
  expect(q(host, "fin-desk-bsk-number-so6").textContent).toBe("KSC/SO-00346");
  expect(host.querySelectorAll('[data-testid^="fin-desk-bsk-row-"]').length).toBe(1);
  await act(async () => { root.unmount(); });
});

test("label tahap SO berbahasa Indonesia", () => {
  expect(stageMeta("Shipped").label).toBe("Dikirim");
  expect(stageMeta("Delivered").label).toBe("Selesai");
});

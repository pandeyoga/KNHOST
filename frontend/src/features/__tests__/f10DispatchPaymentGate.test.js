// F-10 (keputusan owner Q-02, 2026-10-21) — termin CBD/DP menahan kirim: status & kekurangan tampil; tombol
// "Beri pengecualian kirim" hanya untuk pemegang order.release_unpaid dan alasan wajib ≥5 huruf; pengecualian aktif
// dapat dicabut. Termin tanpa DP sebelum kirim → panel tidak tampil.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import DispatchPaymentGatePanel from "../orders/DispatchPaymentGatePanel";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const BLOCKED = { applies: true, blocked: true, term_code: "CBD", term_name: "CBD — Bayar Sebelum Kirim", dp_percent: 100,
  grand_total: 1000000, required: 1000000, paid: 400000, shortfall: 600000, released: null, mode: "block",
  message: "Tertahan pembayaran" };
const FIN = { role: "finance", permissions: { order: ["view", "release_unpaid"] } };
const setVal = (el, v) => {
  Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value").set.call(el, v);
  el.dispatchEvent(new Event("input", { bubbles: true }));
};
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}

beforeEach(() => { axios.get.mockReset(); axios.post.mockReset(); });

test("tertahan: kekurangan tampil; Finance memberi pengecualian dengan alasan ≥5 huruf", async () => {
  axios.get.mockResolvedValue({ data: BLOCKED });
  const released = { ...BLOCKED, blocked: false, released: { by: "Sri", at: "2026-10-21T10:00:00Z", reason: "Transfer sore ini" } };
  axios.post.mockResolvedValue({ data: released });
  const onChanged = jest.fn();
  const { host, root } = await mount(<DispatchPaymentGatePanel orderId="so1" currentUser={FIN} onChanged={onChanged} />);
  expect(axios.get).toHaveBeenCalledWith("/api/sales-orders/so1/dispatch-payment-gate");
  expect(q(host, "so-gate-state").textContent).toMatch(/Tertahan/);
  expect(q(host, "so-gate-shortfall").textContent).toMatch(/600/);
  await act(async () => { q(host, "so-gate-release-open").click(); });
  await act(async () => { setVal(q(host, "so-gate-reason"), "ok"); });
  expect(q(host, "so-gate-confirm").disabled).toBe(true);                        // alasan terlalu pendek
  await act(async () => { setVal(q(host, "so-gate-reason"), "Transfer sore ini"); });
  await act(async () => { q(host, "so-gate-confirm").click(); });
  expect(axios.post).toHaveBeenCalledWith("/api/sales-orders/so1/dispatch-payment-release", { reason: "Transfer sore ini" });
  expect(onChanged).toHaveBeenCalledWith(released);
  expect(q(host, "so-gate-state").textContent).toMatch(/pengecualian berizin/);
  expect(q(host, "so-gate-release-info").textContent).toMatch(/Transfer sore ini/);
  expect(q(host, "so-gate-revoke-open")).not.toBeNull();                          // bisa dicabut
  await act(async () => { root.unmount(); });
});

test("tanpa izin release_unpaid: status tampil, tombol pengecualian tidak ada", async () => {
  const { host, root } = await mount(<DispatchPaymentGatePanel orderId="so1" initial={BLOCKED}
    currentUser={{ role: "warehouse", permissions: { wms: ["view", "dispatch"] } }} testPrefix="outbound-gate" />);
  expect(axios.get).not.toHaveBeenCalled();                                       // data dari daftar Barang Keluar
  expect(q(host, "outbound-gate-state").textContent).toMatch(/Tertahan/);
  expect(q(host, "outbound-gate-release-open")).toBeNull();
  await act(async () => { root.unmount(); });
});

test("termin kredit (tidak menahan) → panel tidak tampil", async () => {
  axios.get.mockResolvedValue({ data: { applies: false, blocked: false } });
  const { host, root } = await mount(<DispatchPaymentGatePanel orderId="so2" currentUser={FIN} />);
  expect(q(host, "so-gate")).toBeNull();
  await act(async () => { root.unmount(); });
});

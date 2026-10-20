// FE-08 / FE-09 (review 2026-10-20) — form retur: respons SO lama tidak menimpa pilihan baru; pemilih SO
// mengambil daftar dari pencarian/paginasi server (bukan 200 SO terbaru yang disaring peramban).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CreateReturnForm from "../sales/CreateReturnForm";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
// Radix Select tidak bisa dioperasikan di jsdom — diganti <select> biasa dengan kontrak yang sama (onValueChange).
jest.mock("../../components/KNSelect", () => (props) => (
  <select data-testid={props["data-testid"]} value={props.value} onChange={(e) => props.onValueChange(e.target.value)}>
    {(props.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const SO = [{ id: "so_a", number: "SO-A", customer_name: "Toko A", status: "shipped" },
            { id: "so_b", number: "SO-B", customer_name: "Toko B", status: "shipped" }];
const ret = (pid, name) => ({ data: { products: [{ product_id: pid, product_name: name, sku: pid, remaining: 10, unit: "yard" }], rolls: [] } });
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const wait = (ms) => act(async () => { await new Promise((r) => setTimeout(r, ms)); });

async function mount() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<CreateReturnForm variant="modal" onCreated={() => {}} onCancel={() => {}} />); });
  await wait(350);   // debounce pencarian awal
  return { host, root };
}
const pick = async (host, value) => {
  const sel = host.querySelector('[data-testid="return-order-select"]');
  await act(async () => { sel.value = value; sel.dispatchEvent(new Event("change", { bubbles: true })); });
};

test("FE-08: A lambat lalu B cepat → form tetap berisi barang SO B", async () => {
  let releaseA;
  axios.get.mockImplementation((url, cfg) => {
    if (url === "/api/sales-returns/eligible-orders") return Promise.resolve({ data: { items: SO, total: 2, has_more: false } });
    if (url === "/api/sales-returns/returnable" && cfg.params.order_id === "so_a") return new Promise((r) => { releaseA = () => r(ret("pa", "Kain A")); });
    if (url === "/api/sales-returns/returnable") return Promise.resolve(ret("pb", "Kain B"));
    return Promise.resolve({ data: {} });
  });
  const { host, root } = await mount();
  await pick(host, "so_a");
  await pick(host, "so_b");
  await flush();
  expect(host.textContent).toContain("Kain B");
  await act(async () => { releaseA(); });   // respons A datang terakhir
  await flush();
  expect(host.textContent).toContain("Kain B");
  expect(host.textContent).not.toContain("Kain A");
  await act(async () => { root.unmount(); });
});

test("FE-09: pilihan SO dari server, pencarian dikirim sebagai ?q= dan halaman berikutnya lewat 'Muat lagi'", async () => {
  axios.get.mockImplementation((url, cfg) => {
    if (url === "/api/sales-returns/eligible-orders") {
      const p = cfg.params;
      if (p.page === 2) return Promise.resolve({ data: { items: [SO[1]], total: 2, page: 2, has_more: false } });
      return Promise.resolve({ data: { items: [SO[0]], total: 2, page: 1, has_more: true } });
    }
    return Promise.resolve({ data: {} });
  });
  const { host, root } = await mount();
  const optionIds = () => [...host.querySelectorAll('[data-testid="return-order-select"] option')].map((o) => o.value).filter(Boolean);
  expect(optionIds()).toEqual(["so_a"]);
  expect(axios.get.mock.calls.some(([u]) => u === "/api/sales-orders")).toBe(false);   // sumber 200-SO lama tidak dipakai
  await act(async () => { host.querySelector('[data-testid="return-order-more"]').click(); });
  await flush();
  expect(optionIds()).toEqual(["so_a", "so_b"]);
  const input = host.querySelector('[data-testid="return-order-search"]');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(input, "Toko B"); input.dispatchEvent(new Event("input", { bubbles: true })); });
  await wait(350);
  const last = axios.get.mock.calls.filter(([u]) => u === "/api/sales-returns/eligible-orders").pop();
  expect(last[1].params).toMatchObject({ q: "Toko B", page: 1 });
  await act(async () => { root.unmount(); });
});

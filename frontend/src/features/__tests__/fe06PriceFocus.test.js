// FE-06 (review 2026-10-20) — Meja Saya → Harga Khusus membuka layar yang dirender DAN pengajuan asalnya.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { rowLink } from "../sales_admin/workDeskApi";
import PriceApprovals from "../sales/PriceApprovals";

jest.mock("../../services/apiClient", () => {
  const get = jest.fn();
  return { __esModule: true, default: { get, post: jest.fn(), patch: jest.fn(), delete: jest.fn() }, API: "/api" };
});
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});   // jsdom tidak punya
const ROWS = [
  { id: "pra_1", status: "pending", customer_name: "Toko A", product_name: "Kain 1", sku: "K1", requested_price: 10000, attachments: [] },
  { id: "pra_2", status: "pending", customer_name: "Toko B", product_name: "Kain 2", sku: "K2", requested_price: 20000, attachments: [] },
];

function mockApi(single) {
  axios.get.mockImplementation((url) => {
    if (url === "/api/price-approvals") return Promise.resolve({ data: ROWS });
    if (url.startsWith("/api/price-approvals/")) return single(url.split("/").pop());
    return Promise.resolve({ data: [] });
  });
}

async function mount(props) {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const root = createRoot(el);
  await act(async () => { root.render(<PriceApprovals {...props} />); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  return { el, root };
}

const manager = { role: "manager", permissions: { price_approval: ["view", "approve", "reject"] } };

test("tautan antrean price_approval menuju layar price-approvals (hub Persetujuan) dengan ID pengajuan", () => {
  const link = rowLink({ ref_type: "price_approval", ref_id: "pra_2", number: "PRA-2" }, "harga_khusus", "me");
  expect(link).toMatchObject({ view: "price-approvals", nav_id: "approval-inbox", focus_type: "price_approval", focus_id: "pra_2" });
});

test("fokus dari antrean menampilkan pengajuan asal saja, lalu fokus dilepas", async () => {
  mockApi((id) => Promise.resolve({ data: ROWS.find((r) => r.id === id) }));
  const onClearFocus = jest.fn();
  const { el, root } = await mount({ currentUser: manager, focusDoc: { focus_type: "price_approval", focus_id: "pra_2" }, onClearFocus });
  expect(el.querySelector('[data-testid="price-approvals-card-pra_2"]')).not.toBeNull();
  expect(el.querySelector('[data-testid="price-approvals-card-pra_1"]')).toBeNull();
  expect(el.querySelector('[data-testid="price-approvals-focus"]')).not.toBeNull();
  expect(el.querySelector('[data-testid="price-approvals-approve-pra_2"]')).not.toBeNull();   // Manager berizin approve
  expect(onClearFocus).toHaveBeenCalled();
  await act(async () => { root.unmount(); });
});

test("pengajuan yang tidak ada / di luar akses: pesan jelas, tidak membuka daftar seolah berhasil", async () => {
  mockApi(() => Promise.reject({ response: { status: 404, data: { detail: "tidak ditemukan" } } }));
  const { el, root } = await mount({ currentUser: manager, focusDoc: { focus_id: "pra_hilang" }, onClearFocus: () => {} });
  expect(el.querySelector('[data-testid="price-approvals-focus-missing"]')).not.toBeNull();
  expect(el.querySelector('[data-testid="price-approvals-focus"]')).toBeNull();
  await act(async () => { root.unmount(); });
});

test("tombol Setujui mengikuti izin price_approval.approve, bukan nama peran", async () => {
  mockApi((id) => Promise.resolve({ data: ROWS.find((r) => r.id === id) }));
  const { el, root } = await mount({ currentUser: { role: "manager", permissions: { price_approval: ["view"] } } });
  expect(el.querySelector('[data-testid="price-approvals-card-pra_1"]')).not.toBeNull();
  expect(el.querySelector('[data-testid="price-approvals-approve-pra_1"]')).toBeNull();
  await act(async () => { root.unmount(); });
});

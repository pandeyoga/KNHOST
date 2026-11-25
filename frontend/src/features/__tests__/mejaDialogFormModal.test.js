// MEJA-12 — §5.3: pop-up periksa & pemenuhan memakai FormModal (INV-UI-11 turun), Esc menutup, aksi tetap sama.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import VerifyOrderDialog from "../sales_admin/VerifyOrderDialog";
import FulfillmentDecisionDialog from "../sales_admin/FulfillmentDecisionDialog";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));

jest.mock("../sales_admin/FulfillmentLineCard", () => ({ value, onChange }) => (
  <button type="button" data-testid="isi-rencana" onClick={() => onChange({ ...value, stock: 1 })}>isi</button>));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset();
});

test("VerifyOrderDialog: cangkang FormModal, Esc menutup, kirim memanggil review-release", async () => {
  routeGet({ "/sales-orders/so1/verification": { verifiable: true, ready: true, checks: [], order_preview: null } });
  mockPost.mockResolvedValue({ data: { released: true, order: { number: "SO-1", status: "confirmed" } } });
  const onClose = jest.fn(); const onVerified = jest.fn();
  await mount(<VerifyOrderDialog orderId="so1" orderNumber="SO-1" customerName="Toko A" onClose={onClose} onVerified={onVerified} />);
  expect(q("verify-dialog").className).toContain("kn-form-modal");
  expect(teks(q("verify-dialog-title"))).toContain("SO-1");
  await klik("verify-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so1/review-release", { note: "", hold: false });
  await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
  expect(onClose).toHaveBeenCalled();
});

test("FulfillmentDecisionDialog: cangkang FormModal", async () => {
  routeGet({ "/sales-admin/orders/so1/fulfillment-plan": { lines: [] } });
  await mount(<FulfillmentDecisionDialog orderId="so1" orderNumber="SO-1" customerName="Toko A" onClose={() => {}} onDecided={() => {}} />);
  expect(q("fulfill-dialog").className).toContain("kn-form-modal");
  expect(q("fulfill-dialog-close")).not.toBeNull();
});

test("tanpa modal-card/modal-overlay buatan sendiri", () => {
  for (const rel of ["../sales_admin/VerifyOrderDialog.jsx", "../sales_admin/FulfillmentDecisionDialog.jsx"]) {
    const src = fs.readFileSync(path.join(__dirname, rel), "utf8");
    expect(src).not.toMatch(/modal-card|modal-overlay/);
  }
});

test("VerifyOrderDialog: galat kirim tetap tampil setelah muat ulang berhasil", async () => {
  routeGet({ "/sales-orders/so1/verification": { verifiable: true, ready: true, checks: [], order_preview: null } });
  mockPost.mockRejectedValue({ response: { data: { detail: "Gagal karena X" } } });
  await mount(<VerifyOrderDialog orderId="so1" orderNumber="SO-1" customerName="Toko A" onClose={() => {}} onVerified={() => {}} />);
  await klik("verify-submit");
  await act(async () => {});
  expect(teks(q("verify-dialog-error"))).toContain("Gagal karena X");
});

test("FulfillmentDecisionDialog: galat eksekusi tetap tampil walau muat ulang tanpa baris", async () => {
  const baris = { product_id: "p1", sku: "S", product_name: "Kain", unit: "yard", backorder_qty: 5, other_entities: [], proposal: [], stock_options: [] };
  let n = 0;
  mockGet.mockImplementation(() => Promise.resolve({ data: { lines: n++ === 0 ? [baris] : [], decisions: [] } }));
  mockPost.mockRejectedValue({ response: { data: { detail: "Sebagian gagal" } } });
  await mount(<FulfillmentDecisionDialog orderId="so1" orderNumber="SO-1" customerName="Toko A" onClose={() => {}} onDecided={() => {}} />);
  expect(q("fulfill-submit")).not.toBeNull();
  await klik("isi-rencana");
  await klik("fulfill-submit");
  await act(async () => {});
  expect(q("fulfill-exec-error")).not.toBeNull();
  expect(teks(q("fulfill-exec-error"))).toContain("Sebagian gagal");
  expect(q("fulfill-submit")).toBeNull();
});

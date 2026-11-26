// LB-T8 R16 — ReceivePaymentModal `cashOnly` (RENDER NYATA, tanpa mock modal): hanya cara bayar tunai, tanpa titipan, payload tanpa titipan.
// (kerangka dari latihS3UangMukaForm; S3 (pelatihan keuangan 18 Nov) — pesanan bertermin DP 50% yang sudah dilepas ke gudang: baris Penagihan menagih UANG
// MUKA, tetapi form Terima pembayaran dulu mengisi alokasi = seluruh sisa pesanan (Rp 2.537.016) — Finance yang langsung
// menyimpan mencatat uang yang belum ditransfer. Kini isian bawaan = yang ditagih sekarang (`due_now` server).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockAssess = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="" />
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
    onChange={(e) => p.onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../finance/payments/paymentApi", () => ({
  assessVariance: (...a) => mockAssess(...a),
  directionMeta: () => ({ label: "", bg: "", fg: "" }), varianceMeta: () => Promise.resolve({ reasons: [] }),
}));

/* eslint-disable import/first */
import ReceivePaymentModal from "../finance/payments/ReceivePaymentModal";
import { invalidatePaymentMethods } from "../../config/paymentMethods";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" }];
const M = (code, name, need = "bank") => ({ code, name, needs_account: need, needs_reference: need === "bank", needs_due_date: false });
const REK = { id: "rek_a", name: "BCA Operasional KSC", bank_name: "BCA", account_number: "741-559-5554", is_default: true };
const SO = { order_id: "so1", number: "KSC/SO-0082", outstanding: 2537016, due_now: 1268508 };
const nbsp = (s) => String(s || "").replace(/ /g, " ");
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);

async function flush(n = 10) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <AppNavProvider role="finance">
        <EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch={false}>{el}<ConfirmHost /></EntityScopeProvider>
      </AppNavProvider>);
  });
  await flush();
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
  await flush(3);
}
function routeGet(deposit) {
  const map = {
    "/payment-methods": [M("transfer", "Transfer bank"), M("cash", "Tunai", "kas")],
    "/ar-receipts/open-orders": [SO], "/ar-receipts/deposit": { deposit_balance: deposit },
    "/bank-accounts/receiving": (cfg) => (cfg?.params?.method === "transfer" ? [REK] : []),
    "/settings/effective": { payment: { wajib_nomor_referensi: false } }, "/cash-holdings/me/summary": { mode: "kas_langsung" },
  };
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    const v = key ? map[key] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg, url) : v });
  });
}
async function simpan() {
  mockPost.mockResolvedValue({ data: { id: "arc_1", number: "KSC/AR-0001", amount: 1, applied_total: 1 } });
  await click(q("ar-receipt-submit"));
  await click(q("ar-receipt-confirm-confirm"));
  await flush();
  const posts = mockPost.mock.calls.filter(([u]) => u === "/api/ar-receipts");
  expect(posts).toHaveLength(1);
  return posts[0][1];
}
beforeEach(() => { mockAssess.mockResolvedValue({ direction: "none", needs_decision: false }); });
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  [mockGet, mockPost, mockAssess].forEach((m) => m.mockReset());
  invalidatePaymentMethods();
  document.body.innerHTML = "";
});


const SO_DUA = { order_id: "so1", number: "KSC/SO-0082", outstanding: 600000 };
test("cashOnly: hanya cara bayar tunai, kotak titipan tidak ada, payload tanpa titipan", async () => {
  SO.due_now = undefined;
  routeGet(500000);
  mockGet.mockImplementation(((orig) => (url, cfg) => {
    if (url.includes("/ar-receipts/open-orders")) return Promise.resolve({ data: [SO_DUA] });
    if (url.includes("/bank-accounts/receiving")) return Promise.resolve({ data: [REK] });   // kas kecil/rekening tunai PT
    return orig(url, cfg);
  })(mockGet.getMockImplementation()));
  await mount(<ReceivePaymentModal customerId="c1" customerName="Toko" preselectOrderId="so1" cashOnly onClose={() => {}} onDone={() => {}} />);
  expect([...q("ar-receipt-method").options].map((o) => o.value).filter(Boolean)).toEqual(["cash"]);
  expect(q("ar-receipt-deposit-box")).toBeNull();
  expect(q("ar-receipt-use-deposit")).toBeNull();
  const body = await simpan();
  expect(body.method).toBe("cash");
  expect(body.use_deposit_amount).toBe(0);
});

test("tanpa cashOnly: kotak titipan tetap ada dan transfer ditawarkan (perilaku lama)", async () => {
  routeGet(500000);
  await mount(<ReceivePaymentModal customerId="c1" customerName="Toko" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  expect(q("ar-receipt-use-deposit")).not.toBeNull();
  expect([...q("ar-receipt-method").options].map((o) => o.value)).toContain("transfer");
});

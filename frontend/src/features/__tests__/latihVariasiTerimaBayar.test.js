// Uji variasi isian pelatihan 18 Nov — form Terima pembayaran:
//  (1) Nominal diterima diketik SELAGI tagihan terbuka dimuat → isian otomatis (sisa tagihan) tidak lagi menimpa /
//      bercampur dengan ketikan ("50.000" dulu menjadi "832.500"); dari baris SO (dibuka) ketikan ≤ sisa → Atur sendiri
//      sebesar ketikan; ketikan > sisa → tetap Tertua dulu (lebih bayar diputus di dialog selisih).
//  (2) Nominal bergaya Indonesia ("3.374.122,50") terkirim persis; minus → alasan "Nominal tidak boleh minus.".
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
const SO = { order_id: "so1", number: "KSC/SO-0021", outstanding: 3440167.5 };
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
const SO2 = { order_id: "so2", number: "KSC/SO-0022", outstanding: 832500 };
let lepasMuat = null;
function routeGet({ tunda = false } = {}) {
  const map = {
    "/payment-methods": [M("transfer", "Transfer bank"), M("cash", "Tunai", "kas")],
    "/ar-receipts/deposit": { deposit_balance: 0 },
    "/bank-accounts/receiving": (cfg) => (cfg?.params?.method === "transfer" ? [REK] : []),
    "/settings/effective": {}, "/cash-holdings/me/summary": {},
  };
  mockGet.mockImplementation((url, cfg) => {
    if (url.includes("/ar-receipts/open-orders")) {
      return tunda ? new Promise((res) => { lepasMuat = () => res({ data: [SO2, SO] }); }) : Promise.resolve({ data: [SO2, SO] });
    }
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
async function ketikHuruf(el, teks) { for (let i = 1; i <= teks.length; i++) await type(el, teks.slice(0, i)); }
beforeEach(() => { mockAssess.mockResolvedValue({ direction: "none", needs_decision: false }); });
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  [mockGet, mockPost, mockAssess].forEach((m) => m.mockReset());
  invalidatePaymentMethods();
  document.body.innerHTML = "";
  lepasMuat = null;
});

test("ketik nominal selagi memuat (tanpa SO dibuka): ketikan tidak ditimpa sisa tagihan", async () => {
  routeGet({ tunda: true });
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 61" onClose={() => {}} onDone={() => {}} />);
  expect(q("ar-receipt-loading")).not.toBeNull();
  await ketikHuruf(q("ar-receipt-amount"), "50.000");
  await act(async () => { lepasMuat(); });
  await flush();
  expect(q("ar-receipt-loading")).toBeNull();
  expect(q("ar-receipt-amount").value).toBe("50.000");
  expect(nbsp(q("ar-receipt-total").textContent)).toBe("Rp 50.000");
  const body = await simpan();
  expect(body.amount).toBe(50000);
});

test("ketik nominal selagi memuat dari baris SO (dibuka): ≤ sisa → Atur sendiri sebesar ketikan", async () => {
  routeGet({ tunda: true });
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 61" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  await ketikHuruf(q("ar-receipt-amount"), "50.000");
  await act(async () => { lepasMuat(); });
  await flush();
  expect(q("ar-receipt-mode-manual").getAttribute("aria-pressed")).toBe("true");
  expect(q("ar-receipt-alloc-so1").value).toBe("50000");
  expect(nbsp(q("ar-receipt-total").textContent)).toBe("Rp 50.000");
  const body = await simpan();
  expect(body.amount).toBe(50000);
  expect(body.allocations).toEqual([{ order_id: "so1", amount: 50000 }]);
});

test("ketik nominal selagi memuat dari baris SO: > sisa → tetap Tertua dulu dengan ketikan (tidak dipotong diam-diam)", async () => {
  routeGet({ tunda: true });
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 61" preselectOrderId="so2" onClose={() => {}} onDone={() => {}} />);
  await ketikHuruf(q("ar-receipt-amount"), "1.000.000");
  await act(async () => { lepasMuat(); });
  await flush();
  expect(q("ar-receipt-mode-auto").getAttribute("aria-pressed")).toBe("true");
  expect(q("ar-receipt-amount").value).toBe("1.000.000");
  expect(nbsp(q("ar-receipt-total").textContent)).toBe("Rp 1.000.000");
});

test("tanpa ketikan: perilaku lama — dari baris SO terisi sisa SO itu", async () => {
  routeGet();
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 61" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  expect(q("ar-receipt-alloc-so1").value).toBe("3440167.5");
  expect(nbsp(q("ar-receipt-total").textContent)).toBe("Rp 3.440.168");
});

test("Tertua dulu: '3.374.122,50' terkirim persis; '-100' → alasan 'Nominal tidak boleh minus.'", async () => {
  routeGet();
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 61" onClose={() => {}} onDone={() => {}} />);
  await type(q("ar-receipt-amount"), "");
  await ketikHuruf(q("ar-receipt-amount"), "-100");
  expect(q("ar-receipt-reason").textContent).toBe("Nominal tidak boleh minus.");
  expect(q("ar-receipt-submit").disabled).toBe(true);
  await type(q("ar-receipt-amount"), "");
  await ketikHuruf(q("ar-receipt-amount"), "3.374.122,50");
  expect(nbsp(q("ar-receipt-total").textContent)).toBe("Rp 3.374.123");
  const body = await simpan();
  expect(body.amount).toBe(3374122.5);
});

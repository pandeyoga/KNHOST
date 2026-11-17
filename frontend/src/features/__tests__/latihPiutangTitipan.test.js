// Pelatihan Keuangan 18 Nov 2026 (F04 "lebih bayar → titipan → dipakai") — form Terima pembayaran, alokasi "Atur
// sendiri" + "Pakai titipan": angka per tagihan = yang dilunasi (uang baru + titipan). Dulu titipan menjadi dana DI LUAR
// alokasi (uang = Σ alokasi) sehingga pesanan tidak bertambah lunas dan kwitansi terbaca "lebih bayar" sebesar titipan.
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
function routeGet(deposit) {
  const map = {
    "/payment-methods": [M("transfer", "Transfer bank"), M("cash", "Tunai", "kas")],
    "/ar-receipts/open-orders": [SO], "/ar-receipts/deposit": { deposit_balance: deposit },
    "/bank-accounts/receiving": (cfg) => (cfg?.params?.method === "transfer" ? [REK] : []),
    "/settings/effective": { payment: { wajib_nomor_referensi: false } }, "/cash-holdings/me/summary": {},
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

test("Atur sendiri + Pakai titipan: titipan ikut melunasi tagihan, uang baru = Σ alokasi − titipan", async () => {
  routeGet(409592.5);
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 21" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  expect(q("ar-receipt-mode-manual").getAttribute("aria-pressed")).toBe("true");
  await click(q("ar-receipt-use-deposit"));
  expect(nbsp(q("ar-receipt-amount-manual").textContent)).toBe("Rp 3.030.575");
  expect(nbsp(q("ar-receipt-amount-manual-note").textContent)).toContain("titipan Rp 409.593");
  expect(nbsp(q("ar-receipt-total").textContent)).toBe("Rp 3.440.168");
  await act(async () => { await new Promise((r) => setTimeout(r, 500)); });
  await flush();
  const takar = mockAssess.mock.calls.at(-1)[0];
  expect(takar).toEqual({ customer_id: "c1", amount: 3030575, use_deposit_amount: 409592.5,
    allocations: [{ order_id: "so1", amount: 3440167.5 }] });
  const body = await simpan();
  expect(body.amount).toBe(3030575);
  expect(body.use_deposit_amount).toBe(409592.5);
  expect(body.allocations).toEqual([{ order_id: "so1", amount: 3440167.5 }]);
  expect(body.account_id).toBe("rek_a");
});

test("Atur sendiri: titipan lebih besar dari alokasi → hanya sebesar alokasi, tanpa uang baru & tanpa rekening", async () => {
  routeGet(5000000);
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 21" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  await click(q("ar-receipt-use-deposit"));
  expect(nbsp(q("ar-receipt-amount-manual").textContent)).toBe("Rp 0");
  expect(q("ar-receipt-account-field")).toBeNull();
  const body = await simpan();
  expect(body.amount).toBe(0);
  expect(body.use_deposit_amount).toBe(3440167.5);
  expect(body.allocations).toEqual([{ order_id: "so1", amount: 3440167.5 }]);
  expect(body.account_id).toBeUndefined();
});

test("Tertua dulu tidak berubah: nominal = uang baru, titipan menambah dana", async () => {
  routeGet(409592.5);
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 21" onClose={() => {}} onDone={() => {}} />);
  expect(q("ar-receipt-mode-auto").getAttribute("aria-pressed")).toBe("true");
  await type(q("ar-receipt-amount"), "3030575");
  await click(q("ar-receipt-use-deposit"));
  expect(nbsp(q("ar-receipt-total").textContent)).toBe("Rp 3.440.168");
  const body = await simpan();
  expect(body.amount).toBe(3030575);
  expect(body.use_deposit_amount).toBe(409592.5);
  expect(body.allocations).toBeUndefined();
});

test("Lebih bayar: pesan selesai menyebut uang yang DITERIMA + rinciannya (melunasi tagihan · jadi titipan)", async () => {
  routeGet(0);
  const onDone = jest.fn();
  await mount(<ReceivePaymentModal customerId="c1" customerName="Latihan 22" onClose={() => {}} onDone={onDone} />);
  await type(q("ar-receipt-amount"), "2000000");
  mockPost.mockResolvedValue({ data: { id: "arc_2", number: "KSC/AR-0035", amount: 2000000, total_funds: 2000000,
    applied_total: 1971027, unapplied_amount: 28973, variance: {} } });
  await click(q("ar-receipt-submit"));
  await click(q("ar-receipt-confirm-confirm"));
  await flush();
  expect(onDone).toHaveBeenCalledTimes(1);
  expect(nbsp(onDone.mock.calls[0][0])).toBe("Kwitansi KSC/AR-0035 (Rp 2.000.000) dicatat untuk Latihan 22. "
    + "Rp 1.971.027 melunasi tagihan, Rp 28.973 menjadi titipan pelanggan.");
});

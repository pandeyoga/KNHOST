// Pelatihan 18 Nov (uji variasi isian V5) — form Bayar pemasok: nominal yang diketik dibaca benar, lebih bayar ditolak
// sebelum simpan, kurang bayar receh (≤ toleransi selisih) disebut sebelum simpan, konfirmasi tidak membulatkan sen.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../../../components/ConfirmHost";
import { EntityScopeProvider } from "../../../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="" />
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
    onChange={(e) => p.onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));

/* eslint-disable import/first */
import PaySupplierModal, { cekNominalBayar, payConfirmText, rpSen } from "../PaySupplierModal";
import { invalidatePaymentMethods } from "../../../../config/paymentMethods";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" }];
const REK = { id: "rek_a", name: "BCA Operasional", bank_name: "BCA", account_number: "777", is_default: true };
const MET = [{ code: "transfer", name: "Transfer bank", needs_account: "bank", needs_reference: true, needs_due_date: false }];
const nb = (s) => String(s || "").replace(/[\u00a0\u202f]/g, " ");
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 10) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch>{el}<ConfirmHost /></EntityScopeProvider>);
  });
  await flush();
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
async function type(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
  await flush(3);
}
async function pick(el, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  [mockGet, mockPost].forEach((m) => m.mockReset());
  invalidatePaymentMethods();
  document.body.innerHTML = "";
});

function routeBill(extra = {}) {
  const map = { "/payment-methods": MET, "/ap-payments/accounts": [REK], "/ap-payments/pending": null,
    "/vendor-bills/vb1": { id: "vb1", bill_number: "VB-1", supplier_name: "Pemasok S", entity_id: "ent_ksc", status: "posted",
      financials: { outstanding: 1864800 }, payment_tolerance: 5000, ...extra } };
  mockGet.mockImplementation((url) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    return Promise.resolve({ data: key ? map[key] : [] });
  });
}

test("cekNominalBayar — lebih bayar diblok, kurang bayar receh disebut, sebagian biasa diam", () => {
  const base = { outstanding: 1864800, tolerance: 5000, type: "vendor_bill" };
  expect(cekNominalBayar({ ...base, amount: 1864800 })).toEqual({ blok: "", info: "" });
  expect(nb(cekNominalBayar({ ...base, amount: 1864900 }).blok))
    .toBe("Nominal Rp 1.864.900 melebihi sisa hutang Rp 1.864.800. Bayar paling banyak sebesar sisa hutang.");
  expect(cekNominalBayar({ ...base, amount: 2000000 }).blok).toMatch(/melebihi sisa hutang/);
  expect(nb(cekNominalBayar({ ...base, amount: 1864000 }).info)).toMatch(/^Kurang Rp 800 dari sisa hutang — masih di dalam toleransi selisih Rp 5\.000/);
  expect(cekNominalBayar({ ...base, amount: 500000 })).toEqual({ blok: "", info: "" });   // sebagian biasa: sisa tetap hutang
  expect(cekNominalBayar({ ...base, amount: 1864000, type: "contra_bon" }).info).toBe("");   // kontrabon tanpa tutup otomatis
  expect(cekNominalBayar({ ...base, amount: 1864000, tolerance: 0 }).info).toBe("");
  expect(nb(rpSen(1764800.5))).toBe("Rp 1.764.800,5");
  expect(nb(rpSen(7000000))).toBe("Rp 7.000.000");
  expect(nb(payConfirmText({ amount: 33883.5, supplier: "S", account: "BCA", pt: "Sukacita" }))).toBe("Bayar Rp 33.883,5 ke S dari BCA untuk Sukacita?");
});

test("form — koma sen & spasi ribuan terbaca; lebih bayar → tombol mati beralasan; kurang receh → catatan + konfirmasi", async () => {
  routeBill();
  mockPost.mockResolvedValue({ data: { id: "vb1", status: "posted", payments: [] } });
  await mount(<PaySupplierModal target={{ type: "vendor_bill", id: "vb1" }} onClose={() => {}} onPaid={() => {}} />);
  await pick(q("pay-supplier-account"), "rek_a");
  expect(q("pay-supplier-amount").value).toBe("1864800");
  expect(q("pay-supplier-modal").textContent).toContain("kecuali selisih receh");

  await type(q("pay-supplier-amount"), "1764800,5");
  expect(q("pay-supplier-submit").disabled).toBe(false);
  await click(q("pay-supplier-submit"));
  expect(nb(q("pay-supplier-confirm-message").textContent)).toMatch(/^Bayar Rp 1\.764\.800,5 ke Pemasok S dari /);
  await click(q("pay-supplier-confirm-cancel"));

  await type(q("pay-supplier-amount"), "1 864 800");
  expect(q("pay-supplier-submit").disabled).toBe(false);

  await type(q("pay-supplier-amount"), "1864900");
  expect(q("pay-supplier-submit").disabled).toBe(true);
  expect(nb(q("pay-supplier-reason").textContent)).toBe("Nominal Rp 1.864.900 melebihi sisa hutang Rp 1.864.800. Bayar paling banyak sebesar sisa hutang.");

  await type(q("pay-supplier-amount"), "1864000");
  expect(q("pay-supplier-submit").disabled).toBe(false);
  expect(nb(q("pay-supplier-variance-note").textContent)).toMatch(/Kurang Rp 800 .* DITUTUP otomatis/);
  await click(q("pay-supplier-submit"));
  expect(nb(q("pay-supplier-confirm-message").textContent)).toMatch(/\? Kurang Rp 800 dari sisa hutang/);
  await click(q("pay-supplier-confirm-confirm"));
  const posts = mockPost.mock.calls.filter(([u]) => u === "/api/vendor-bills/vb1/pay");
  expect(posts).toHaveLength(1);
  expect(posts[0][1].amount).toBe(1864000);
});

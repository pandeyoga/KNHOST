// MEJA-9 — §5.4: terbit faktur pajak selalu lewat pratinjau + konfirmasi, di meja dan di layar asal.
// R5: galat server tampil di dalam pop-up; kedua pemanggil memanggil workDeskApi.issueTaxInvoice langsung.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import FinanceDesk from "../finance/FinanceDesk";
import { OrderDetailPanel } from "../orders/OrderDetailPanel";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, className }) => (
    <select data-testid={tid} className={className} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../components/KNDatePicker", () => {
  const M = ({ value, onChange, "data-testid": tid }) => (
    <input data-testid={tid} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />);
  return { __esModule: true, default: M, KNDatePicker: M };
});
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../home/ReturnDeskSummaryCard", () => ({
  __esModule: true, ...jest.requireActual("../home/ReturnDeskSummaryCard"),
  default: () => <div data-testid="return-desk-stub" />,
}));
jest.mock("../finance/payments/ReceivePaymentModal", () => () => null);
jest.mock("../documents/ProcessTimeline", () => () => null);
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../documents/RelatedDocsPanel", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);
jest.mock("../finance/payments/SoPaymentPanel", () => () => null);
jest.mock("../orders/DispatchPaymentGatePanel", () => () => null);
jest.mock("../orders/PodProgressNote", () => () => null);
jest.mock("../orders/SoApprovalsPanel", () => () => null);
jest.mock("../orders/OrderFulfillmentBadges", () => () => null);
jest.mock("../orders/OrderIntercoSupplyPanel", () => () => null);
jest.mock("../orders/OrderTransferLinks", () => () => null);
jest.mock("../orders/RestockPanel", () => () => null);
jest.mock("../finance/amendments/AmendmentTrailPanel", () => () => null);
jest.mock("../orders/OrderFeedbackPanel", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
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
  mockGet.mockReset(); mockPost.mockReset(); mockToast.mockReset();
  sessionStorage.clear();
});

function berkasSumber(dir = path.join(__dirname, "..", "..")) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = path.join(dir, d.name);
    if (d.isDirectory()) return d.name === "__tests__" ? [] : berkasSumber(p);
    return /\.jsx?$/.test(d.name) ? [p] : [];
  });
}
const baca = (f) => fs.readFileSync(f, "utf8");

const BARIS = { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko A", value: 1110000, ppn_amount: 110000,
  dpp: 1000000, customer_npwp: "01.234.567.8-901.000", entity_id: "ent_ksc", action: "Terbitkan", action_kind: "issue_tax", age_days: 1 };
const DESK = { queues: [{ id: "siap_faktur_pajak", label: "Faktur", count: 1, rows: [BARIS] }], not_my_desk: [] };
const FIN = { permissions: { payment_variance: ["decide"], tax_invoice: ["create"] } };

test("meja: klik Terbitkan membuka pratinjau, belum menerbitkan; Terbitkan di pop-up memanggil endpoint yang sama", async () => {
  routeGet({ "/finance/desk": DESK, "/settings/effective": { tax: { kode_transaksi_diizinkan: ["01", "04"] } } });
  mockPost.mockResolvedValue({ data: { number: "KSC/FKT-00009" } });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-faktur_pajak-action-so1");
  expect(mockPost).not.toHaveBeenCalled();
  const pv = teks(q("fkt-issue-preview"));
  for (const s of ["SO-1", "Toko A", "01.234.567.8-901.000", "110.000", "1.000.000", "1.110.000"]) expect(pv).toContain(s);
  expect(teks(q("fkt-modal-submit"))).toBe("Terbitkan");
  await klik("fkt-modal-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so1/tax-invoice",
    expect.objectContaining({ kode_transaksi: null, nsfp: null, faktur_date: expect.any(String) }));
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("KSC/FKT-00009") }));
  expect(q("fkt-modal")).toBeNull();
});

test("galat server tampil di dalam pop-up; pop-up tetap terbuka; tanpa toast", async () => {
  routeGet({ "/finance/desk": DESK, "/settings/effective": {} });
  mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Masa pajak November sudah dilaporkan." } } });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-faktur_pajak-action-so1"); await klik("fkt-modal-submit");
  expect(teks(q("fkt-modal-error"))).toContain("Masa pajak November sudah dilaporkan.");
  expect(q("fkt-modal")).not.toBeNull();
  expect(mockToast).not.toHaveBeenCalled();
});

test("NPWP tidak tercatat: barisnya tidak tampil, tanpa 'Belum tercatat'", async () => {
  routeGet({ "/finance/desk": { queues: [{ ...DESK.queues[0], rows: [{ ...BARIS, customer_npwp: "" }] }] }, "/settings/effective": {} });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-faktur_pajak-action-so1");
  const pv = teks(q("fkt-issue-preview"));
  expect(pv).not.toContain("NPWP"); expect(pv).not.toContain("Belum tercatat");
});

test("layar asal (rincian pesanan): tombol Terbitkan Faktur Pajak membuka pop-up yang sama dulu", async () => {
  const onRefresh = jest.fn();
  routeGet({ "/tax-invoices": [], "/settings/effective": { tax: { pemicu_faktur: "pesanan" } } });
  mockPost.mockResolvedValue({ data: { number: "KSC/FKT-00010" } });
  const SO = { id: "so_s1", number: "KSC/SO-S1", customer_name: "Toko S1", status: "done", entity_id: "ent_ksc", is_pkp: true,
    items: [], total_amount: 250000, net_subtotal: 250000, dpp: 250000, ppn_amount: 27500, grand_total: 277500 };
  await mount(<OrderDetailPanel order={SO} user={{ role: "finance", permissions: { tax_invoice: ["view", "create"], order: ["view"] } }}
    embedded onRefresh={onRefresh} />);
  await klik("issue-tax-invoice-btn");
  expect(mockPost).not.toHaveBeenCalled(); expect(q("fkt-issue-preview")).not.toBeNull();
  await klik("fkt-modal-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so_s1/tax-invoice", expect.objectContaining({ kode_transaksi: null }));
  expect(q("fkt-modal")).toBeNull();
  expect(onRefresh).toHaveBeenCalled();
});

test("setiap pemanggil terbit faktur memakai TaxIssueDialog", () => {
  const pola = /\bissueTaxInvoice\(|\bonIssueTaxInvoice\(|tax-invoices\/\$\{[^}]+\}\/issue/;
  const salah = berkasSumber().filter((f) => pola.test(baca(f)) && !baca(f).includes("TaxIssueDialog"));
  expect(salah).toEqual([]);
});

test("URL mentah terbit faktur pesanan (/tax-invoice) hanya di workDeskApi.js (dan TaxIssueDialog.jsx)", () => {
  const url = /sales-orders\/\$\{[^}]+\}\/tax-invoice|["'`]\/tax-invoice["'`]/;
  const boleh = ["sales_admin/workDeskApi.js", "finance/TaxIssueDialog.jsx"];
  const salah = berkasSumber().filter((f) => !boleh.some((k) => f.endsWith(k)) && url.test(baca(f))).map((f) => path.basename(f));
  expect(salah).toEqual([]);
});

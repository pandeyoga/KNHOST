// Meja gelombang 2 · Tugas 4 — §5.7a sisi piutang: nomor dokumen di Piutang, Penagihan, Kwitansi, Kartu pelanggan,
// Faktur Keluaran, Selisih bayar & Denda menjadi `DocLink` (klik → `openDocPreview({docType, docId, number})`).
// Baris tanpa id dokumen / pengguna tanpa izin baca → teks biasa (bukan tautan mati). Tombol "Jejak" tetap ada.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import AppNavContext from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const mockGet = jest.fn();
const mockTrace = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../documents/trace/traceDeepLink", () => ({ openTrace: (...a) => mockTrace(...a), TRACE_EVENT: "kn:trace" }));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../../components/StoreCreditBadge", () => () => null);
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../finance/payments/PenaltyPanel", () => ({ __esModule: true, default: () => null }));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
}));
jest.mock("../../components/KNMonthPicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
  formatPeriodId: (v) => v,
}));
jest.mock("../../components/PaginationBar", () => (p) => <div data-testid={p.testId}>{p.total}</div>);

/* eslint-disable import/first */
import ARAgingDetail from "../finance/ARAgingDetail";
import CollectionWorklist from "../crm/CollectionWorklist";
import ARReceiptsHistory from "../crm/ARReceiptsHistory";
import CustomerBillingTab from "../crm/CustomerBillingTab";
import CustomerStatementTab from "../crm/CustomerStatementTab";
import TaxInvoices from "../finance/TaxInvoices";
import PaymentVarianceQueue from "../finance/payments/PaymentVarianceQueue";
import { invalidatePaymentMethods } from "../../config/paymentMethods";
/* eslint-enable import/first */

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
const preview = jest.fn();
const ENTS = [{ id: "ent_ksc", short_name: "KSC", legal_name: "PT Kain Suka Cita" }];
const nav = (extra = {}) => ({
  openDocument: () => {}, openCustomerCard: () => {}, cardsEnabled: true, previewsEnabled: true, openDocPreview: preview, ...extra,
});
async function mount(el, navExtra) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <AppNavContext.Provider value={nav(navExtra)}>
        <EntityScopeProvider selectedEntity="ent_ksc" entities={ENTS} canSwitch>{el}</EntityScopeProvider>
      </AppNavContext.Provider>,
    );
  });
  await flush();
  return host;
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(3); }
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    const v = key ? map[key] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg) : v });
  });
}
beforeAll(() => setAccessContext({ role: "admin" }));
afterAll(() => setAccessContext(null));
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  [mockGet, mockTrace, preview].forEach((m) => m.mockReset());
  invalidatePaymentMethods();
});

const P_SO = { order: ["view"] };
const P_SO_AR = { order: ["view"], ar_receipt: ["view"] };
const user = (permissions) => ({ role: "x", permissions });

// ---------- 1. Piutang › rincian umur -----------------------------------------------------------------
const AGING = { customer_name: "Toko DP", totals: { total: 3000000, ar_ledger: 3000000, exposure: 0 }, penalties: [],
  items: [{ order_id: "so2", order_number: "SO-DP", due_date: "2026-11-03", days_late: 17, overdue: true, grand_total: 2000000,
    paid_total: 0, outstanding: 2000000, ar_ledger: 2000000, exposure: 0, denda_estimate: 0, penalties: [], entity_id: "ent_ksc",
    lines: [{ sumber: "surat_jalan", ref_id: "shp1", ref_number: "SJ-9", tanggal: "2026-11-06", jatuh_tempo: "2026-11-20",
      nilai: 400000, terbayar: 0, sisa: 400000, hari_lewat: 0, jurnal_id: "", line_id: "ppl_sj" }] }] };

test("Piutang: nomor pesanan di baris & jadwal tagihan membuka pratinjau; Jejak jadwal tetap ada", async () => {
  await mount(<ARAgingDetail detail={AGING} customerId="cus1" loading={false} currentUser={user(P_SO)}
    onAccrue={() => {}} onRefresh={() => {}} onClose={() => {}} />);
  await click(q("ar-aging-order-so2"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so2", number: "SO-DP", entityId: "ent_ksc" });
  await click(q("ar-schedule-doc-so2-surat_jalan"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so2", number: "SO-DP", entityId: "ent_ksc" });
  await click(q("ar-schedule-trace-so2-surat_jalan"));
  expect(mockTrace).toHaveBeenCalledWith({ docType: "sales_order", docId: "so2", number: "SO-DP" });
});

test("Piutang: tanpa izin order.view nomor pesanan teks biasa", async () => {
  await mount(<ARAgingDetail detail={AGING} customerId="cus1" loading={false} currentUser={user({})}
    onAccrue={() => {}} onRefresh={() => {}} onClose={() => {}} />);
  expect(q("ar-aging-order-so2")).toBeNull();
  expect(norm(q("ar-aging-order-so2-text").textContent)).toBe("SO-DP");
});

// ---------- 2. Penagihan & Penerimaan -----------------------------------------------------------------
test("Penagihan: nomor pesanan dulu tautan mati kini membuka pratinjau; tanpa order_id teks biasa", async () => {
  routeGet({
    "/collection-reminders": [
      { order_id: "so1", order_number: "SO-1", customer_id: "c1", customer_name: "Toko A", outstanding: 100000, due_date: "2026-11-01",
        days_late: 3, overdue: true, sales_name: "Ayu", entity_id: "ent_ksc" },
      { order_id: "", order_number: "SO-X", customer_id: "c2", customer_name: "Toko B", outstanding: 5000, due_date: "2026-11-02",
        days_late: 1, overdue: true, sales_name: "Ayu" }],
    "/ar-receipts": { items: [], total: 0 },
  });
  await mount(<CollectionWorklist currentUser={user(P_SO)} selectedEntity="ent_ksc" />);
  const row = q("collection-row-so1");
  expect(row).not.toBeNull();
  await click(q("collection-order-so1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so1", number: "SO-1", entityId: "ent_ksc" });
  // baris tanpa id: key pada order_id kosong → cari lewat teks
  expect(document.body.textContent).toContain("SO-X");
  expect(document.body.querySelectorAll('button[data-testid^="collection-order-"]').length).toBe(1);
});

// ---------- 3. Kwitansi (riwayat) ----------------------------------------------------------------------
const RECEIPTS = { items: [
  { id: "r1", number: "AR-1", customer_name: "Toko Maju", method: "transfer", payment_method_code: "transfer", amount: 1500000,
    status: "recorded", receipt_date: "2026-11-10", entity_id: "ent_ksc", variance: {},
    allocations: [{ order_id: "so1", order_number: "KSC/SO-1", applied: 1000000 }, { order_id: "", order_number: "SO-LAMA", applied: 500000 }] }],
  total: 1, page: 1, page_size: 25 };

test("Kwitansi: nomor kwitansi & tiap pesanan teralokasi jadi DocLink sendiri; alokasi tanpa order_id teks biasa; Jejak tetap", async () => {
  routeGet({ "/payment-methods": [{ code: "transfer", name: "Transfer bank", needs_account: "bank" }], "/ar-receipts": RECEIPTS,
    "/settings/effective": {} });
  await mount(<ARReceiptsHistory refreshKey={0} selectedEntity="ent_ksc" currentUser={user(P_SO_AR)} />);
  await click(q("ar-history-number-r1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "ar_receipt", docId: "r1", number: "AR-1", entityId: "ent_ksc" });
  await click(q("ar-history-order-r1-so1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so1", number: "KSC/SO-1", entityId: "ent_ksc" });
  expect(norm(q("ar-history-allocs-r1").textContent)).toBe("KSC/SO-1, SO-LAMA");
  expect(document.body.querySelectorAll('button[data-testid^="ar-history-order-r1-"]').length).toBe(1);   // SO-LAMA = teks
  await click(q("ar-history-trace-r1"));
  expect(mockTrace).toHaveBeenCalledWith({ docType: "ar_receipt", docId: "r1", number: "AR-1" });
});

// ---------- 4a. Kartu pelanggan › Tagihan --------------------------------------------------------------
test("Kartu pelanggan › Tagihan: nomor pesanan membuka pratinjau; Jejak jadwal tetap tersedia", async () => {
  routeGet({ "/billing-schedule": { total: 1, totals: { outstanding: 100 }, items: [
    { order_id: "so1", order_number: "SO-1", seq: 1, line_id: "l1", kind_label: "Surat jalan", amount: 100, paid_amount: 0,
      outstanding: 100, days_late: 2, due_date: "2026-11-01" }] } });
  await mount(<CustomerBillingTab customer={{ id: "c1", entity_id: "ent_ksc" }} currentUser={user({ ...P_SO, payment_plan: ["view"] })}
    selectedEntity="ent_ksc" show="schedule" />);
  await click(q("customer-billing-doc-so1-1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so1", number: "SO-1", entityId: "ent_ksc" });
  await click(q("customer-billing-trace-so1-1"));
  expect(mockTrace).toHaveBeenCalledWith({ docType: "sales_order", docId: "so1", number: "SO-1" });
});

// ---------- 4b. Kartu pelanggan › Rekening koran -------------------------------------------------------
const ROW = (o) => ({ date: "2026-10-01", doc_label: "X", description: "d", debit: 1, credit: 0, balance: 1, je_id: "je", je_number: "JE-1", ...o });
test("Rekening koran: hanya sales_order & ar_receipt jadi DocLink; jenis lain tetap tombol Jejak", async () => {
  routeGet({ "/statement": { customer: { id: "c1" }, from: "2026-10-01", to: "2026-10-31", opening_balance: 0, closing_balance: 1,
    rows: [
      ROW({ je_id: "je_so", doc_id: "so1", doc_number: "SO-1", trace_type: "sales_order" }),
      ROW({ je_id: "je_ar", doc_id: "ar1", doc_number: "AR-1", trace_type: "ar_receipt" }),
      ROW({ je_id: "je_sj", doc_id: "shp1", doc_number: "SJ-1", trace_type: "shipment" }),
      ROW({ je_id: "je_nd", doc_id: "", doc_number: "", trace_type: "sales_order" })],
    penalties: { opening_balance: 0, rows: [], closing_balance: 0 } } });
  await mount(<CustomerStatementTab customer={{ id: "c1", name: "Toko", entity_id: "ent_ksc" }}
    currentUser={user({ ...P_SO_AR, credit_profile: ["view"] })} selectedEntity="ent_ksc" />);
  const t = "customer-statement-table";
  await click(q(`${t}-doc-je_so`));
  expect(preview).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so1", number: "SO-1", entityId: "ent_ksc" });
  await click(q(`${t}-doc-je_ar`));
  expect(preview).toHaveBeenLastCalledWith({ docType: "ar_receipt", docId: "ar1", number: "AR-1", entityId: "ent_ksc" });
  expect(preview).toHaveBeenCalledTimes(2);
  await click(q(`${t}-doc-je_sj`));                                     // surat jalan: tetap Jejak
  expect(mockTrace).toHaveBeenLastCalledWith({ docType: "shipment", docId: "shp1", number: "SJ-1" });
  expect(preview).toHaveBeenCalledTimes(2);
  await click(q(`${t}-trace-je_so`));                                   // Jejak berdampingan dengan DocLink
  expect(mockTrace).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so1", number: "SO-1" });
  expect(q(`${t}-doc-je_nd`)).toBeNull();                               // tanpa id → bukan tautan
});

// ---------- 8. Faktur Keluaran -------------------------------------------------------------------------
const FKT = { id: "f1", number: "FKT-1", status: "terbit", doc_kind: "faktur", trigger: "surat_jalan", order_id: "so1",
  order_number: "SO-1", shipment_no: "SJ-1", entity_id: "ent_ksc", kode_transaksi: "04", customer_id: "cus1", customer_name: "Toko Uji",
  ppn_rate: 12, ppn_amount: 30000, grand_total: 280000, dpp: 250000, net_subtotal: 250000, faktur_date: "2026-11-14",
  data_incomplete: [], customer_tax: { id_type: "npwp", id_number: "0123456789012345" },
  items: [{ product_name: "Katun A", sku: "KA-01", quantity: 10, unit: "meter", price: 25000, subtotal: 250000, line_total: 250000 }] };

test("Faktur Keluaran: nomor pesanan membuka pratinjau (tak pindah layar); rincian memuat tabel barang", async () => {
  routeGet({ "/tax-invoices": [FKT], "/tax/output-reconciliation": {}, "/settings/effective": { tax: {} } });
  const openDocument = jest.fn();
  await mount(<TaxInvoices currentUser={user({ ...P_SO, tax_invoice: ["view"] })} />, { openDocument });
  await click(q("fkt-source-f1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so1", number: "SO-1", entityId: "ent_ksc" });
  expect(openDocument).not.toHaveBeenCalled();
  await click(q("fkt-detail-f1"));
  const lines = norm(q("fkt-detail-lines").textContent);
  expect(lines).toContain("Katun A");
  expect(lines).toContain("KA-01");
});

// ---------- 9. Selisih bayar & Denda -------------------------------------------------------------------
test("Selisih bayar: nomor kwitansi membuka pratinjau; Jejak tetap", async () => {
  routeGet({ "/payment-variances/meta": { reasons: [] }, "/payment-variances": {
    items: [], stats: {}, pending: [{ receipt_id: "r1", number: "AR-1", customer_name: "Toko A", direction: "short", delta: -100,
      funds: 1000, entity_id: "ent_ksc", receipt_date: "2026-11-10" }] } });
  await mount(<PaymentVarianceQueue currentUser={user({ ar_receipt: ["view"] })} selectedEntity="ent_ksc" />);
  await click(q("pv-pending-doc-r1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "ar_receipt", docId: "r1", number: "AR-1", entityId: "ent_ksc" });
  await click(q("pv-pending-trace-r1"));
  expect(mockTrace).toHaveBeenCalledWith({ docType: "ar_receipt", docId: "r1", number: "AR-1" });
});

describe("Denda", () => {
  const { default: Panel } = jest.requireActual("../finance/payments/PenaltyPanel");
  const nota = (id, o) => ({ id, number: `DN-${id}`, status: "draft", amount: 1000, paid_amount: 0, customer_id: "c1", customer_name: "Toko A",
    line_label: "Surat jalan SJ-1", due_date: "2026-10-01", days_late: 3, billable_days: 3, explain: [], entity_id: "ent_ksc",
    policy_snapshot: { sources: {} }, ...o });
  test("dasar denda sales_order → DocLink pesanan; jenis lain / tanpa id tidak jadi tautan", async () => {
    const rows = [nota("1", { doc_type: "sales_order", doc_id: "so1", doc_number: "SO-1" }),
      nota("2", { doc_type: "plan", doc_id: "p1", doc_number: "RPB-1" }),
      nota("3", { doc_type: "sales_order", doc_id: "", doc_number: "SO-2" })];
    await mount(<Panel rows={rows} currentUser={user({ ...P_SO, penalty: ["view"] })} />);
    await click(q("penalty-base-1"));
    expect(preview).toHaveBeenLastCalledWith({ docType: "sales_order", docId: "so1", number: "SO-1", entityId: "ent_ksc" });
    expect(q("penalty-base-2")).toBeNull();
    expect(q("penalty-base-3")).toBeNull();
    await click(q("penalty-trace-1"));                                   // Jejak nota denda tetap
    expect(mockTrace).toHaveBeenCalledWith({ docType: "penalty", docId: "1", number: "DN-1" });
  });
});

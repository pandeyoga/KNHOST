// Meja gelombang 2 · Tugas 5 — §5.7a sisi hutang & kas: nomor tagihan/kontrabon di Hutang per Pemasok, faktur di rincian
// Kontrabon, tabel barang di Kartu pemasok (tagihan & retur beli), dan kolom "Sumber" + "Jurnal" di Transaksi Kas.
// Baris tanpa id / jenis tanpa pratinjau / pengguna tanpa izin baca → teks biasa. Tombol "Jejak" tetap ada.
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
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(), askReason: jest.fn(), askText: jest.fn(), askChoice: jest.fn(), default: {},
}));
jest.mock("@/services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(), askReason: jest.fn(), askText: jest.fn(), askChoice: jest.fn(), default: {},
}));
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
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/PaginationBar", () => (p) => <div data-testid={p.testId}>{p.total}</div>);

/* eslint-disable import/first */
import APSupplierDetail from "../finance/ap/APSupplierDetail";
import { BillsSection } from "../purchasing/contrabon/ContraBonParts";
import Supplier360Panel from "../purchasing/Supplier360Panel";
import CashManagementView, { CASH_REF_DOC } from "../purchasing/CashManagementView";
/* eslint-enable import/first */

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
const preview = jest.fn();
const ENTS = [{ id: "ent_ksc", short_name: "KSC", legal_name: "PT Kain Suka Cita" }];
const nav = (extra = {}) => ({
  openDocument: () => {}, go: () => {}, canOpen: () => false, cardsEnabled: true, previewsEnabled: true, openDocPreview: preview, ...extra,
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
});

const user = (permissions) => ({ role: "x", permissions });
const P_AP = { vendor_bill: ["view"], contra_bon: ["view"], supplier: ["view"] };

// ---------- 1. Hutang per Pemasok ---------------------------------------------------------------------
const AP_DETAIL = { supplier: { id: "s1", name: "Pemasok 91", code: "S-91" }, entities: [{ id: "ent_ksc", label: "KSC" }],
  totals: { outstanding: 100, overdue: 0, payable_direct: 100, held: 0, bill_count: 2 },
  bills: [
    { bill_id: "vb1", bill_number: "VB-1", supplier_invoice_no: "INV-1", po_number: "PO-1", entity_id: "ent_ksc", due_date: "2026-12-17",
      days_past_due: -3, aging_bucket: "not_due", grand_total: 100, amount_paid: 0, outstanding: 100, contra_bon: null },
    { bill_id: "", bill_number: "VB-LAMA", supplier_invoice_no: "", po_number: "", entity_id: "ent_ksc", due_date: "2026-12-17",
      days_past_due: -3, aging_bucket: "not_due", grand_total: 5, amount_paid: 0, outstanding: 5, contra_bon: null }],
  contra_bons: [{ id: "cb1", number: "KB-1", entity_id: "ent_ksc", status: "approved", status_label: "Disetujui", bill_count: 1,
    net_payable: 100, outstanding: 100, payable: false }],
  credits: { items: [] } };

test("Hutang per pemasok: nomor tagihan & kontrabon membuka pratinjau; Jejak tetap; tanpa id teks biasa", async () => {
  await mount(<APSupplierDetail detail={AP_DETAIL} loading={false} currentUser={user(P_AP)} selectedEntity="ent_ksc" onClose={() => {}} />);
  await click(q("ap-detail-bill-doc-vb1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "vendor_bill", docId: "vb1", number: "VB-1", entityId: "ent_ksc" });
  await click(q("ap-detail-bill-trace-vb1"));
  expect(mockTrace).toHaveBeenLastCalledWith({ docType: "vendor_bill", docId: "vb1", number: "VB-1" });
  await click(q("ap-detail-cb-doc-cb1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "contra_bon", docId: "cb1", number: "KB-1", entityId: "ent_ksc" });
  await click(q("ap-detail-cb-trace-cb1"));
  expect(mockTrace).toHaveBeenLastCalledWith({ docType: "contra_bon", docId: "cb1", number: "KB-1" });
  expect(document.body.querySelectorAll('button[data-testid^="ap-detail-bill-doc-"]').length).toBe(1);   // VB-LAMA = teks
  expect(document.body.textContent).toContain("VB-LAMA");
});

test("Hutang per pemasok: tanpa izin baca tagihan/kontrabon nomor teks biasa (tanpa warna tautan)", async () => {
  await mount(<APSupplierDetail detail={AP_DETAIL} loading={false} currentUser={user({})} selectedEntity="ent_ksc" onClose={() => {}} />);
  expect(q("ap-detail-bill-doc-vb1")).toBeNull();
  expect(norm(q("ap-detail-bill-doc-vb1-text").textContent)).toBe("VB-1");
  expect(q("ap-detail-cb-doc-cb1")).toBeNull();
  expect(norm(q("ap-detail-cb-doc-cb1-text").textContent)).toBe("KB-1");
});

// ---------- 2. Kontrabon › faktur yang ditukar --------------------------------------------------------
const CB = { id: "cb1", entity_id: "ent_ksc", decisions: [], bills: [
  { bill_id: "vb1", bill_number: "VB-1", supplier_invoice_no: "F-1", po_number: "PO-1", due_date: "2026-12-01", applied_amount: 100, grand_total: 100, match: {} },
  { bill_id: "", bill_number: "VB-X", supplier_invoice_no: "", po_number: "", due_date: "2026-12-01", applied_amount: 5, grand_total: 5, match: {} }] };

test("Kontrabon: nomor faktur membuka pratinjau tagihan; tanpa id / tanpa izin teks biasa", async () => {
  await mount(<BillsSection cb={CB} perms={P_AP} />);
  await click(q("cb-bill-doc-vb1"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "vendor_bill", docId: "vb1", number: "VB-1", entityId: "ent_ksc" });
  expect(document.body.querySelectorAll('button[data-testid^="cb-bill-doc-"]').length).toBe(1);
  expect(document.body.textContent).toContain("VB-X");
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  await mount(<BillsSection cb={CB} perms={{}} />);
  expect(q("cb-bill-doc-vb1")).toBeNull();
  expect(norm(q("cb-bill-doc-vb1-text").textContent)).toBe("VB-1");
});

// ---------- 3. Kartu pemasok › rincian barang ---------------------------------------------------------
const SUP = { id: "s1", name: "Pemasok S", code: "S1", entity_id: "ent_ksc", status: "active", sections_allowed: ["tagihan", "retur"],
  payables: null, contra_bons: null, payments: null, documents: [], price_history: [], purchase_orders: null, landed_costs: null,
  bills: [{ id: "vb1", bill_number: "VB-1", status: "posted", bill_date: "2026-11-01", entity_id: "ent_ksc",
    financials: { grand_total: 150000, outstanding: 0 },
    items: [{ product_name: "Katun A", sku: "KA-01", billed_qty: 10, unit: "meter", price: 15000, line_total: 150000 }] }],
  returns: [{ id: "pr1", debit_note_number: "ND-1", status: "posted", created_at: "2026-11-02", total_amount: 30000,
    items: [{ product_name: "Rayon B", sku: "RB-02", quantity: 3, unit: "roll", price: 10000, subtotal: 30000 }] }] };

test("Kartu pemasok: pop-up tagihan memuat tabel barang 5 kolom", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/suppliers/s1/360") ? SUP : [] }));
  await mount(<Supplier360Panel variant="card" supplierId="s1" currentUser={user({ ...P_AP })} selectedEntity="ent_ksc" />);
  await click(q("supplier-360-bill-vb1").querySelector("button"));
  const t = q("record-detail-items");
  expect(t).not.toBeNull();
  expect([...t.querySelectorAll("th")].map((x) => norm(x.textContent))).toEqual(["Barang", "SKU", "Ditagih", "Harga", "Jumlah"]);
  const cells = [...t.querySelectorAll("tbody td")].map((x) => norm(x.textContent));
  expect(cells[0]).toBe("Katun A");
  expect(cells[1]).toBe("KA-01");
  expect(cells[2]).toContain("10");
  expect(cells[3]).toMatch(/15\.000/);
  expect(cells[4]).toMatch(/150\.000/);
});

test("Kartu pemasok: pop-up retur beli memuat tabel barang 5 kolom (jumlah + satuan)", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/suppliers/s1/360") ? SUP : [] }));
  await mount(<Supplier360Panel variant="card" supplierId="s1" currentUser={user({ ...P_AP, purchase_return: ["view"] })} selectedEntity="ent_ksc" />);
  await click(q("supplier-360-tab-retur") || [...document.body.querySelectorAll("button")].find((b) => norm(b.textContent) === "Retur"));
  await click(q("supplier-360-list-returns-row-pr1"));
  const t = q("record-detail-items");
  expect(t).not.toBeNull();
  expect([...t.querySelectorAll("th")].map((x) => norm(x.textContent))).toEqual(["Barang", "SKU", "Jumlah", "Harga", "Subtotal"]);
  const cells = [...t.querySelectorAll("tbody td")].map((x) => norm(x.textContent));
  expect(cells[0]).toBe("Rayon B");
  expect(cells[2]).toMatch(/3\s*roll/);
  expect(cells[4]).toMatch(/30\.000/);
});

// ---------- 4. Transaksi Kas ---------------------------------------------------------------------------
const CASH_ALL = { cash: ["view", "create", "delete"], accounting: ["view"], ar_receipt: ["view"], vendor_bill: ["view"],
  contra_bon: ["view"], sales_return: ["view"] };
const txn = (o) => ({ id: `t_${o.ref_type}`, number: `KSC/CASH-${o.ref_type}`, cash_type: "kas_besar", direction: "in", amount: 1000,
  category: "pembelian", description: "uji", entity_id: "ent_ksc", txn_date: "2026-11-10T03:00:00Z", status: "posted",
  ref_number: "", ...o });
const CASH_ROWS = [
  txn({ ref_type: "ar_receipt", ref_id: "r1", ref_number: "AR-1", journal_entry_id: "je1" }),
  txn({ ref_type: "vendor_bill", ref_id: "vb1", ref_number: "VB-1", direction: "out" }),
  txn({ ref_type: "ap_advance", ref_id: "vb1", ref_number: "VB-1", direction: "out" }),
  txn({ ref_type: "contra_bon", ref_id: "cb1", ref_number: "KB-1", direction: "out" }),
  txn({ ref_type: "sales_return", ref_id: "sr1", ref_number: "RJ-1", direction: "out", source_entity_id: "ent_ksc" }),
  txn({ ref_type: "purchase_return", ref_id: "pr1", ref_number: "ND-1" }),
  txn({ ref_type: "penalty", ref_id: "pen1", ref_number: "DN-1" }),
  txn({ ref_type: "manual", ref_id: "kunci", direction: "out" }),
  txn({ id: "t_lama", ref_type: "ar_receipt", ref_id: "", ref_number: "AR-LAMA" })];
const JE = { id: "je1", number: "JU-1", date: "2026-11-10", description: "Kas kwitansi", source_type: "ar_receipt", entity_id: "ent_ksc",
  total_debit: 1000, total_credit: 1000, created_by: "sys",
  lines: [{ account_code: "1-1210", account_name: "Bank", debit: 1000, credit: 0 }, { account_code: "1-1300", account_name: "Piutang", debit: 0, credit: 1000 }] };
function routeCash() {
  routeGet({
    "/cash-transactions/summary": { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {}, counts: { all: 9, kas_kecil: 0, kas_besar: 9 } },
    "/cash-transactions": { items: CASH_ROWS, total: 9, page: 1, page_size: 50, has_more: false },
    "/gl/journal/je1": JE,
    "/entities": ENTS,
  });
}

test("Peta sumber kas: hanya rujukan yang id-nya terbukti id dokumen terdaftar", () => {
  expect(CASH_REF_DOC).toEqual({ ar_receipt: "ar_receipt", vendor_bill: "vendor_bill", ap_advance: "vendor_bill",
    contra_bon: "contra_bon", sales_return: "sales_return" });
});

test("Transaksi Kas: kolom Sumber membuka pratinjau untuk jenis terpetakan; jenis lain & tanpa id teks biasa", async () => {
  routeCash();
  await mount(<CashManagementView currentUser={user(CASH_ALL)} selectedEntity="ent_ksc" />);
  await click(q("cash-source-t_ar_receipt"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "ar_receipt", docId: "r1", number: "AR-1", entityId: "ent_ksc" });
  await click(q("cash-source-t_vendor_bill"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "vendor_bill", docId: "vb1", number: "VB-1", entityId: "ent_ksc" });
  await click(q("cash-source-t_ap_advance"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "vendor_bill", docId: "vb1", number: "VB-1", entityId: "ent_ksc" });
  await click(q("cash-source-t_contra_bon"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "contra_bon", docId: "cb1", number: "KB-1", entityId: "ent_ksc" });
  await click(q("cash-source-t_sales_return"));
  expect(preview).toHaveBeenLastCalledWith({ docType: "sales_return", docId: "sr1", number: "RJ-1", entityId: "ent_ksc" });
  // retur beli & denda: tak ada pratinjau → teks nomor; kas manual tak punya sumber
  expect(q("cash-source-t_purchase_return")).toBeNull();
  expect(norm(q("cash-source-t_purchase_return-text").textContent)).toContain("ND-1");
  expect(q("cash-source-t_penalty")).toBeNull();
  expect(norm(q("cash-source-t_penalty-text").textContent)).toContain("DN-1");
  expect(q("cash-source-row-t_manual")).toBeNull();
  expect(preview).toHaveBeenCalledTimes(5);
});

test("Transaksi Kas: tanpa izin baca jenis dokumen sumber → teks biasa", async () => {
  routeCash();
  await mount(<CashManagementView currentUser={user({ cash: ["view"] })} selectedEntity="ent_ksc" />);
  expect(q("cash-source-t_ar_receipt")).toBeNull();
  expect(norm(q("cash-source-t_ar_receipt-text").textContent)).toContain("AR-1");
});

test("Transaksi Kas: tautan Jurnal hanya bila journal_entry_id ada & izin accounting.view; membuka rincian jurnal", async () => {
  routeCash();
  await mount(<CashManagementView currentUser={user(CASH_ALL)} selectedEntity="ent_ksc" />);
  expect(q("cash-journal-t_vendor_bill")).toBeNull();      // tanpa journal_entry_id
  await click(q("cash-journal-t_ar_receipt"));
  expect(mockGet.mock.calls.some(([u]) => u === "/api/gl/journal/je1")).toBe(true);
  expect(q("gl-journal-detail")).not.toBeNull();
  expect(norm(q("gl-journal-detail").textContent)).toContain("JU-1");
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  routeCash();
  await mount(<CashManagementView currentUser={user({ ...CASH_ALL, accounting: [] })} selectedEntity="ent_ksc" />);
  expect(q("cash-journal-t_ar_receipt")).toBeNull();
});

test("Transaksi Kas: jurnal gagal dimuat → pesan galat, bukan pop-up kosong", async () => {
  routeCash();
  mockGet.mockImplementation((url) => (url === "/api/gl/journal/je1"
    ? Promise.reject({ response: { status: 404, data: { detail: "Jurnal tidak ditemukan" } } })
    : Promise.resolve({ data: url.includes("/summary") ? { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {}, counts: { all: 9 } }
      : url === "/api/cash-transactions" ? { items: CASH_ROWS, total: 9, page: 1, page_size: 50, has_more: false } : [] })));
  await mount(<CashManagementView currentUser={user(CASH_ALL)} selectedEntity="ent_ksc" />);
  await click(q("cash-journal-t_ar_receipt"));
  expect(q("gl-journal-detail")).toBeNull();
  expect(document.body.textContent).toContain("Jurnal tidak ditemukan");
});

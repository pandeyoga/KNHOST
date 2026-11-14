// PK-17 (IA-01, IA-03, IA-09) — layar mengikuti penyaringan nominal dari server (docs/blueprint/unit/PK-17.md).
//   U15 — Meja Finance: `/home/finance` dijawab 403 → papan `fin-home-*` tidak digambar, `fin-desk-error` tidak tampil.
//   U16 — Jejak Dokumen: simpul ber-`amount_hidden` menulis "Nilai disembunyikan"; tombol buka simpul itu mati
//         (TraceGraph) dan hasil pencarian tidak menampilkan nominal (TraceSearch).
//   U17 — Kontrabon: tanpa `vendor_bill.view` tab "Daftar Kontrabon" tidak ada dan tab aktif "GR Belum Ditagih";
//         dengan izin itu tiga tab.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import FinanceDesk from "../finance/FinanceDesk";
import TraceGraph from "../documents/trace/TraceGraph";
import TraceSearch from "../documents/trace/TraceSearch";
import ContraBonsView from "../purchasing/contrabon/ContraBonsView";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti isian polos; komponen berat yang tidak diuji di sini diganti kosong.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../sales_admin/SoTrackerCard", () => () => null);
jest.mock("../crm/ARReceiptModal", () => () => null);
jest.mock("../purchasing/contrabon/ContraBonDetailPanel", () => () => null);
jest.mock("../purchasing/contrabon/ContraBonCreateWizard", () => () => null);
jest.mock("../purchasing/contrabon/ExchangeScheduleModal", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const qAll = (prefix) => [...document.body.querySelectorAll(`[data-testid^="${prefix}"]`)];
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<EntityScopeProvider selectedEntity="ent_ksc" entities={ENTS}>{el}</EntityScopeProvider>);
  });
  await flush();
  return host;
}
/** `map`: akhiran URL → data (atau galat `{ status }`). Kunci terpanjang menang. */
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    const v = hit ? map[hit] : [];
    if (v && v.__status) {
      return Promise.reject(Object.assign(new Error("ditolak"), {
        response: { status: v.__status, data: { detail: v.detail || "" } } }));
    }
    return Promise.resolve({ data: v });
  });
}

afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset();
  document.body.innerHTML = "";
});

// ── U15 ────────────────────────────────────────────────────────────────────────────────────────────────────────────
test("PK17 U15 — Meja Finance: papan 403 tidak digambar dan tidak ada pesan galat", async () => {
  routeGet({
    "/home/finance": { __status: 403, detail: "Anda belum punya akses untuk melihat antrean hutang pemasok." },
    "/finance/desk": { queues: [], totals: {}, not_my_desk: [] },
  });
  await mount(<FinanceDesk currentUser={{ role: "driver", permissions: {} }} selectedEntity="ent_ksc" />);
  expect(mockGet.mock.calls.some(([u]) => u.endsWith("/home/finance"))).toBe(true);
  expect(q("finance-desk")).not.toBeNull();
  expect(qAll("fin-home-")).toHaveLength(0);
  expect(q("fin-desk-error")).toBeNull();
});

test("PK17 U15b — Meja Finance: galat selain 403 tetap menggambar papan 'tidak bisa dibaca' (regresi B5)", async () => {
  routeGet({
    "/home/finance": { __status: 500 },
    "/finance/desk": { queues: [], totals: {}, not_my_desk: [] },
  });
  await mount(<FinanceDesk currentUser={{ role: "finance", permissions: {} }} selectedEntity="ent_ksc" />);
  expect(q("fin-home-boards")).not.toBeNull();
});

// ── U16 ────────────────────────────────────────────────────────────────────────────────────────────────────────────
const node = (over) => ({
  key: `${over.doc_type}:${over.doc_id}`, label: over.doc_type, title: "Pemasok PK17", status: "draft",
  date: "2026-11-10", entity_id: "ent_ksc", order: 20, level: 0, link: { view: "x", focus_type: over.doc_type,
    focus_id: over.doc_id }, pdf_doc_type: over.doc_type, ...over,
});
const PO = node({ doc_type: "purchase_order", doc_id: "po_x", number: "PO-UJI-PK17", amount: 25000000, is_anchor: true });
const VB = node({ doc_type: "vendor_bill", doc_id: "vb_x", number: "VB-UJI-PK17X", amount: null,
  amount_hidden: true, can_open: false, pdf_doc_type: "", order: 30 });
const TRACE = {
  anchor: PO, nodes: [PO, VB], edges: [{ from: PO.key, to: VB.key, rel: "child", rel_label: "Menurunkan" }],
  groups: [{ doc_type: "purchase_order", label: "Purchase Order", order: 20, docs: [PO] },
    { doc_type: "vendor_bill", label: "Tagihan Supplier", order: 30, docs: [VB] }],
  node_count: 2, edge_count: 1, depth: 3,
};

test("PK17 U16 — TraceGraph: simpul tersembunyi bertulis 'Nilai disembunyikan' dan tombol bukanya mati", async () => {
  const onOpen = jest.fn();
  await mount(<TraceGraph trace={TRACE} onAnchor={() => {}} onOpen={onOpen} />);
  const vb = q("trace-node-vb_x");
  expect(vb.textContent).toContain("Nilai disembunyikan");
  expect(vb.textContent).toContain("Peran Anda tidak punya akses lihat modul dokumen ini.");
  expect(vb.textContent).not.toMatch(/Rp/);
  const buka = q("trace-open-vb_x");
  expect(buka.disabled).toBe(true);
  await act(async () => { buka.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  expect(onOpen).not.toHaveBeenCalled();
  expect(q("trace-pdf-view-vb_x")).toBeNull();
  // Simpul yang boleh dilihat tetap bernominal dan bisa dibuka.
  expect(q("trace-node-po_x").textContent).toMatch(/25\.000\.000/);
  expect(q("trace-open-po_x").disabled).toBe(false);
});

test("PK17 U16 — TraceSearch: hasil tersembunyi bertulis 'Nilai disembunyikan' tanpa nominal", async () => {
  routeGet({ "/documents/trace-search": [{ ...VB, ref_count: 1 }, { ...PO, ref_count: 1 }] });
  await mount(<TraceSearch entityId="ent_ksc" onPick={() => {}} />);
  const input = q("trace-search-input");
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => {
    setter.call(input, "PK17");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { await new Promise((r) => setTimeout(r, 450)); });
  await flush();
  const vb = q("trace-result-vb_x");
  expect(vb).not.toBeNull();
  expect(vb.textContent).toContain("Nilai disembunyikan");
  expect(vb.textContent).not.toMatch(/Rp/);
  expect(q("trace-result-po_x").textContent).toMatch(/25\.000\.000/);
});

// ── U17 ────────────────────────────────────────────────────────────────────────────────────────────────────────────
const SUMMARY_HIDDEN = {
  waiting_count: 1, waiting_value: null, scheduled_count: 0, scheduled_value: null, due_soon_count: 0,
  due_soon_value: null, disputed_count: 0, disputed_value: null, overdue_count: 0, unbilled_gr_value: null,
  unbilled_gr_po_count: 0, unbilled_gr_overdue: 0, sla_days: 2, amount_hidden: true,
};
function routeContraBon(summary) {
  routeGet({
    "/contra-bons/meta": { statuses: [], reasons: [] },
    "/contra-bons": [],
    "/contra-bons/summary": summary,
    "/contra-bons/status-counts": { all: 1, submitted: 1 },
    "/contra-bons/unbilled-receipts": { rows: [], total_value: null, po_count: 0, overdue_count: 0,
      age_threshold_days: 14, amount_hidden: true },
    "/contra-bons/exchange-schedules": summary.amount_hidden
      ? { rows: [{ supplier_id: "s1", supplier_name: "Pemasok PK17", invoice_exchange: { mode: "none" },
        billable_count: 1, billable_value: null, unbilled_gr_value: null, unbilled_gr_po_count: 0 }],
      due_soon: [], amount_hidden: true }
      : { rows: [], due_soon: [] },
  });
}
const tabKeys = () => qAll("cb-tab-").map((el) => el.getAttribute("data-testid"));
const activeTab = () => document.body.querySelector('[data-testid^="cb-tab-"][aria-selected="true"]')
  ?.getAttribute("data-testid");

test("PK17 U17 — Kontrabon tanpa vendor_bill.view: tanpa tab Daftar, tab aktif GR Belum Ditagih, nilai '—'", async () => {
  routeContraBon(SUMMARY_HIDDEN);
  const gudang = { role: "warehouse", permissions: { contra_bon: ["view"] } };
  await mount(<ContraBonsView currentUser={gudang} selectedEntity="ent_ksc" entities={ENTS} />);
  expect(tabKeys()).toEqual(["cb-tab-unbilled", "cb-tab-schedules"]);
  expect(document.body.textContent).not.toContain("Daftar Kontrabon");
  expect(activeTab()).toBe("cb-tab-unbilled");
  expect(q("cb-unbilled-tab")).not.toBeNull();
  expect(q("cb-unbilled-total").textContent).toBe("—");
  expect(q("cb-kpi-unbilled-value").textContent.trim()).toBe("—");
  expect(q("cb-summary").textContent).not.toMatch(/Rp/);
  expect(q("cb-kpi-waiting").textContent).toBe("1");
  await act(async () => { q("cb-tab-schedules").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
  expect(q("cb-sched-billable").textContent.trim()).toBe("—");
  expect(q("cb-sched-unbilled").textContent.trim()).toBe("—");
});

test("PK17 U17 — Kontrabon dengan vendor_bill.view: tiga tab, tab awal Daftar Kontrabon", async () => {
  routeContraBon({ ...SUMMARY_HIDDEN, waiting_value: 10000000, scheduled_value: 0, due_soon_value: 0,
    disputed_value: 0, unbilled_gr_value: 0, amount_hidden: undefined });
  const keu = { role: "manager", permissions: { contra_bon: ["view"], vendor_bill: ["view"] } };
  await mount(<ContraBonsView currentUser={keu} selectedEntity="ent_ksc" entities={ENTS} />);
  expect(tabKeys()).toEqual(["cb-tab-list", "cb-tab-unbilled", "cb-tab-schedules"]);
  expect(activeTab()).toBe("cb-tab-list");
  expect(q("cb-summary").textContent).toMatch(/10\.000\.000/);
});

// Pola UI gelombang Pembelian (docs/blueprint/04_POLA_UI.md §2.A, disetujui pemilik 16 Nov) — lima layar daftar
// Pembelian (PO, PR, Tagihan Supplier, Order Makloon, Retur ke Supplier) memakai templat Daftar:
//   · kartu angka = saringan cepat (aktif bila dipilih, klik lagi = semua), menyaring PERSIS seperti tab lama;
//   · status (dan status bayar PO) dipilih lewat DROPDOWN dengan jumlah yang sama — tidak ada deret tab/chip saringan;
//   · tombol buat ada di bilah daftar tepat di atas tabel, bukan di kepala halaman.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import PurchaseOrderManagement from "../admin/PurchaseOrderManagement";
import PurchaseRequisitions from "../purchasing/PurchaseRequisitions";
import VendorBillsView from "../purchasing/VendorBillsView";
import MakloonOrdersView from "../purchasing/MakloonOrdersView";
import PurchaseReturns from "../purchasing/PurchaseReturns";

const mockGet = jest.fn();
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
// Pemilih radix diganti <select> polos (pola `masukan16NovOD.test.js`) supaya nilainya bisa dipilih di jsdom.
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, disabled }) => (
    <select data-testid={tid} value={value ?? ""} disabled={disabled} onChange={(e) => onValueChange(e.target.value)}>
      {!options.some((o) => o.value === "") && <option value="" />}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
// Bagian berat yang tidak diuji di sini. ExportMenu tiruan memperlihatkan saringan yang diteruskan ke Pusat Export.
jest.mock("../../components/LineFilter", () => () => null);
jest.mock("../../components/ExportMenu", () => (p) => (
  <span data-testid={p.testId} data-filters={JSON.stringify((p.filters || []).filter(Boolean))} />
));
jest.mock("../purchasing/MakloonOrderDetailPanel", () => (p) => <div data-testid="stub-mko-detail">{p.mkoId}</div>);
jest.mock("../purchasing/makloon/MakloonWizard", () => () => null);
jest.mock("../purchasing/ReturnDetailPanel", () => () => null);
jest.mock("../purchasing/RollPickerModal", () => () => null);
jest.mock("../purchasing/VendorBillCreateModal", () => () => null);
jest.mock("../purchasing/VendorBillDetailPanel", () => (p) => <div data-testid="stub-vb-detail">{p.bill?.bill_number}</div>);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
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
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function pilih(el, v) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, v);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
/** Router GET: kunci = akhir URL (terpanjang menang); nilai = data atau fungsi (params) → data. */
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    const v = hit ? map[hit] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg?.params || {}) : v });
  });
}
/** Parameter permintaan daftar berhalaman (membawa `page`) terakhir ke `path`. */
const lastList = (path) => [...mockGet.mock.calls].reverse()
  .find(([u, c]) => u === `/api${path}` && c?.params?.page)?.[1].params;
const optLabel = (testId, v) => [...q(testId).options].find((o) => o.value === v)?.textContent;
const rowIds = (prefix) => [...document.body.querySelectorAll(`[data-testid^="${prefix}"]`)].map((r) => r.getAttribute("data-testid"));
const pressed = (testId) => q(testId).getAttribute("aria-pressed");

/** Tombol buat di bilah daftar (bukan kepala halaman), dan tidak ada deret tab status. */
function expectCreateInToolbar(toolbarId, createId) {
  const btn = q(createId);
  expect(btn).not.toBeNull();
  expect(q(toolbarId).contains(btn)).toBe(true);
  expect(document.body.querySelector(".view-header").contains(btn)).toBe(false);
  expect(document.body.querySelector(".tab-bar")).toBeNull();
}

afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset();
  document.body.innerHTML = "";
});

// ── Pesanan Pembelian (PO) ──────────────────────────────────────────────────────────────────────────────────────────
describe("Pesanan Pembelian — kartu, dropdown status/status bayar, centang terlambat", () => {
  const COUNTS = { waiting_approval: 2, pending: 1, receiving: 1, partial: 1, completed: 3, closed_short: 1, rejected: 1 };
  const USER = { name: "Admin", permissions: { purchase_order: ["view", "create"] } };

  test("kartu & dropdown menyaring dengan kunci tab lama; tombol buat di bilah daftar", async () => {
    routeGet({
      "/purchase-orders/status-counts": { by_status: COUNTS, total: 10 },
      "/purchase-orders": { items: [], total: 0, has_more: false },
    });
    await mount(<PurchaseOrderManagement user={USER} selectedEntity="ent_ksc" />);
    expectCreateInToolbar("po-toolbar", "create-po-button");
    expect(q("po-payment-chip-all")).toBeNull();   // deret chip status bayar diganti dropdown
    expect(lastList("/purchase-orders").status).toBeUndefined();

    // Kartu = saringan cepat (kunci sama dengan tab lama); klik lagi = semua.
    await click(q("po-metric-approval"));
    expect(lastList("/purchase-orders").status).toBe("waiting_approval");
    expect(pressed("po-metric-approval")).toBe("true");
    expect(q("po-status-filter").value).toBe("approval");
    await click(q("po-metric-inbound"));
    expect(lastList("/purchase-orders").status).toBe("pending,receiving,partial");
    await click(q("po-metric-inbound"));
    expect(lastList("/purchase-orders").status).toBeUndefined();
    expect(pressed("po-metric-inbound")).toBe("false");

    // Dropdown status: jumlah = jumlah tab lama; pilihan menyaring server dengan kelompok status yang sama.
    expect(optLabel("po-status-filter", "")).toBe("Semua status (10)");
    expect(optLabel("po-status-filter", "inbound")).toBe("Menunggu / Proses Terima (3)");
    expect(optLabel("po-status-filter", "done")).toBe("Selesai (4)");
    expect(optLabel("po-status-filter", "closed")).toBe("Ditolak / Batal (1)");
    await pilih(q("po-status-filter"), "done");
    expect(lastList("/purchase-orders").status).toBe("completed,closed_short");
    expect(pressed("po-metric-done")).toBe("true");

    // Status bayar = dropdown; tanpa status terpilih hanya PO hidup (G4-30), hitungan tanpa PO Ditolak/Batal.
    await pilih(q("po-status-filter"), "");
    expect(optLabel("po-payment-filter", "unpaid")).toBe("Belum Bayar (9)");
    expect(optLabel("po-payment-filter", "")).toBe("Semua status bayar (10)");
    await pilih(q("po-payment-filter"), "unpaid");
    expect(lastList("/purchase-orders")).toMatchObject({
      payment: "unpaid", status: "waiting_approval,pending,receiving,partial,completed,closed_short" });

    // "Terlambat" = centang di bilah daftar (bukan tombol merah buatan).
    expect(q("po-filter-late").getAttribute("type")).toBe("checkbox");
    await click(q("po-filter-late"));
    expect(lastList("/purchase-orders").late).toBe(1);
  });
});

// ── Permintaan Pembelian (PR) ───────────────────────────────────────────────────────────────────────────────────────
describe("Permintaan Pembelian — kartu & dropdown status, bilah gabung kontekstual", () => {
  const PRS = [
    { id: "p1", number: "PR-001", status: "pending_approval", items: [{ product_name: "Benang" }] },
    { id: "p2", number: "PR-002", status: "approved", items: [{ product_id: "x", product_name: "Grey", quantity: 10 }] },
    { id: "p3", number: "PR-003", status: "converted", items: [{ product_name: "Kain" }] },
  ];
  test("kartu & dropdown menyaring seperti tab lama; tombol buat di bilah daftar", async () => {
    routeGet({
      "/purchase-requisitions/merge-suggestions": { groups: [] },
      "/purchase-requisitions": (p) => ({ items: p.status ? PRS.filter((r) => r.status === p.status) : PRS,
        by_status: { pending_approval: 1, approved: 1, converted: 1 } }),
    });
    await mount(<PurchaseRequisitions currentUser={{ permissions: { purchase_order: ["create"] } }} selectedEntity="ent_ksc" />);
    expectCreateInToolbar("pr-toolbar", "pr-create-btn");
    expect(rowIds("pr-row-")).toEqual(["pr-row-p1", "pr-row-p2", "pr-row-p3"]);
    expect(q("pr-toolbar-count").textContent).toBe("3 PR");

    await click(q("pr-metric-pending"));
    expect(rowIds("pr-row-")).toEqual(["pr-row-p1"]);
    expect(q("pr-status-filter").value).toBe("pending_approval");
    expect(pressed("pr-metric-pending")).toBe("true");

    expect(optLabel("pr-status-filter", "approved")).toBe("Disetujui (1)");
    await pilih(q("pr-status-filter"), "approved");
    expect(rowIds("pr-row-")).toEqual(["pr-row-p2"]);
    expect(pressed("pr-metric-approved")).toBe("true");

    // Bilah gabung = bilah aksi kontekstual: hanya muncul bila ada PR dicentang.
    expect(q("pr-merge-bar")).toBeNull();
    await click(q("pr-pick-p2"));
    expect(q("pr-merge-bar")).not.toBeNull();
  });
});

// ── Tagihan Supplier ────────────────────────────────────────────────────────────────────────────────────────────────
describe("Tagihan Supplier — kartu umur hutang menyaring, dropdown status", () => {
  const MGR = { role: "manager", permissions: { vendor_bill: ["view", "create", "pay"] } };
  const SERVER = [{ id: "vbd", bill_number: "VB-D", status: "draft", supplier_name: "CV A", entity_id: "ent_ksc",
    items: [], grand_total: 1000, financials: { outstanding: 1000 } }];
  const SUMMARY = {
    total_outstanding: 3000, aging: { not_due: 0, "1-30": 1000, "31-60": 0, "61-90": 0, ">90": 2000 },
    aging_labels: [{ key: "not_due", label: "Belum jatuh tempo" }, { key: "1-30", label: "1–30 hari" },
      { key: "31-60", label: "31–60 hari" }, { key: "61-90", label: "61–90 hari" }, { key: ">90", label: "> 90 hari" }],
    by_supplier: [],
    bills: [
      { bill_id: "vb2", bill_number: "VB-2", supplier_name: "CV C", status: "posted", grand_total: 2000, outstanding: 2000,
        aging_bucket: ">90", days_past_due: 120, po_number: "PO-2" },
      { bill_id: "vb1", bill_number: "VB-1", supplier_name: "CV B", status: "posted", grand_total: 1000, outstanding: 1000,
        aging_bucket: "1-30", days_past_due: 12, po_number: "PO-1" },
    ],
  };
  test("kartu umur = saringan cepat atas tagihan berhutang; dropdown status = tab lama; buat di bilah", async () => {
    routeGet({
      "/vendor-bills": { items: SERVER, total: 1, has_more: false },
      "/vendor-bills/status-counts": { all: 3, draft: 1, posted: 2 },
      "/vendor-bills/payables/summary": SUMMARY,
      "/vendor-bills/vb1": { id: "vb1", bill_number: "VB-1", status: "posted", items: [] },
      "/purchase-orders": [],
    });
    await mount(<VendorBillsView currentUser={MGR} selectedEntity="ent_ksc" />);
    expectCreateInToolbar("vb-toolbar", "create-vendor-bill-button");
    expect(rowIds("vb-row-")).toEqual(["vb-row-vbd"]);

    await click(q("vb-summary-over-90"));
    expect(rowIds("vb-row-")).toEqual(["vb-row-vb2"]);
    expect(pressed("vb-summary-over-90")).toBe("true");
    expect(q("vb-toolbar-count").textContent).toBe("1 tagihan berhutang");
    expect(q("vb-row-vb2").textContent).toContain("lewat 120 hari");
    await click(q("vb-summary-total"));
    expect(rowIds("vb-row-")).toEqual(["vb-row-vb2", "vb-row-vb1"]);
    await click(q("vb-summary-total"));   // klik lagi → daftar biasa
    expect(rowIds("vb-row-")).toEqual(["vb-row-vbd"]);
    expect(pressed("vb-summary-total")).toBe("false");

    // Dropdown status = tab lama (saringan server, jumlah dari status-counts).
    expect(optLabel("vb-status-filter", "posted")).toBe("Terposting (belum lunas) (2)");
    await pilih(q("vb-status-filter"), "posted");
    expect(lastList("/vendor-bills").status).toBe("posted");

    // Baris kartu umur membawa ringkasan saja — rincian diambil dari server saat dibuka.
    await click(q("vb-summary-1-30"));
    expect(q("vb-status-filter").value).toBe("all");
    await click(q("vb-open-vb1"));
    expect(mockGet).toHaveBeenCalledWith("/api/vendor-bills/vb1");
    expect(q("stub-vb-detail").textContent).toBe("VB-1");
  });
});

// ── Order Makloon ───────────────────────────────────────────────────────────────────────────────────────────────────
describe("Order Makloon — kartu & dropdown status, Unduh + buat di bilah, tautan Meja MD", () => {
  const ORDERS = [
    { id: "m1", mko_number: "MKO-1", status: "draft", steps: [] },
    { id: "m2", mko_number: "MKO-2", status: "in_process", steps: [] },
    { id: "m3", mko_number: "MKO-3", status: "partially_received", steps: [] },
    { id: "m4", mko_number: "MKO-4", status: "completed", steps: [] },
  ];
  const USER = { permissions: { makloon_order: ["view", "create"] } };
  test("kartu Diproses = in_process + diterima sebagian; dropdown = tab lama", async () => {
    routeGet({ "/makloon-orders": ORDERS });
    await mount(<MakloonOrdersView currentUser={USER} selectedEntity="ent_ksc" />);
    expectCreateInToolbar("mko-filters", "create-makloon-order-button");
    expect(q("mko-filters").contains(q("mko-export"))).toBe(true);
    expect(rowIds("mko-row-")).toEqual(["mko-row-m1", "mko-row-m2", "mko-row-m3", "mko-row-m4"]);

    await click(q("mko-stat-process"));
    expect(rowIds("mko-row-")).toEqual(["mko-row-m2", "mko-row-m3"]);
    expect(pressed("mko-stat-process")).toBe("true");
    expect(JSON.parse(q("mko-export").getAttribute("data-filters"))).toEqual([["status", "in", ["in_process", "partially_received"]]]);

    expect(optLabel("mko-status-filter", "partially_received")).toBe("Diterima sebagian (1)");
    await pilih(q("mko-status-filter"), "partially_received");
    expect(rowIds("mko-row-")).toEqual(["mko-row-m3"]);
    expect(JSON.parse(q("mko-export").getAttribute("data-filters"))).toEqual([["status", "eq", "partially_received"]]);
    await click(q("mko-stat-all"));
    expect(rowIds("mko-row-")).toHaveLength(4);
  });

  test("tautan dokumen (focusDoc, mis. dari Meja MD) tetap membuka rincian order makloon", async () => {
    routeGet({ "/makloon-orders": ORDERS, "/makloon-orders/m3": ORDERS[2] });
    const onClearFocus = jest.fn();
    await mount(<MakloonOrdersView currentUser={USER} selectedEntity="ent_ksc"
      focusDoc={{ focus_type: "makloon_order", focus_id: "m3" }} onClearFocus={onClearFocus} />);
    expect(q("stub-mko-detail").textContent).toBe("m3");
    expect(onClearFocus).toHaveBeenCalled();
  });
});

// ── Retur ke Supplier ───────────────────────────────────────────────────────────────────────────────────────────────
describe("Retur ke Supplier — kartu & dropdown status", () => {
  const RETS = [
    { id: "r1", number: "PRT-1", status: "draft", items: [] },
    { id: "r2", number: "PRT-2", status: "pending_approval", items: [] },
    { id: "r3", number: "PRT-3", status: "approved", items: [] },
  ];
  test("kartu & dropdown menyaring server seperti tab lama; tombol buat di bilah daftar", async () => {
    routeGet({
      "/purchase-returns/status-counts": { all: 3, draft: 1, pending_approval: 1, approved: 1 },
      "/purchase-returns": (p) => {
        const items = p.status ? RETS.filter((r) => r.status === p.status) : RETS;
        return { items, total: items.length, has_more: false };
      },
    });
    await mount(<PurchaseReturns currentUser={{ permissions: {} }} selectedEntity="ent_ksc" />);
    expectCreateInToolbar("pret-toolbar", "create-return-button");
    expect(rowIds("return-row-")).toEqual(["return-row-r1", "return-row-r2", "return-row-r3"]);

    await click(q("pret-stat-pending_approval"));
    expect(lastList("/purchase-returns").status).toBe("pending_approval");
    expect(rowIds("return-row-")).toEqual(["return-row-r2"]);
    expect(q("pret-status-filter").value).toBe("pending_approval");
    expect(pressed("pret-stat-pending_approval")).toBe("true");
    await click(q("pret-stat-all"));
    expect(lastList("/purchase-returns").status).toBeUndefined();
    expect(q("pret-status-filter").value).toBe("all");

    expect(optLabel("pret-status-filter", "approved")).toBe("Disetujui (1)");
    await pilih(q("pret-status-filter"), "approved");
    expect(lastList("/purchase-returns").status).toBe("approved");
    expect(rowIds("return-row-")).toEqual(["return-row-r3"]);
    expect(pressed("pret-stat-approved")).toBe("true");
  });
});

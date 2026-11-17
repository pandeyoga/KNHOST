// Pola UI gelombang Gudang (pemilik 16 Nov — docs/blueprint/masukan-pemilik/2026-11-16_UI_MEJA_DAN_MENU.md):
// M26 Operasi Gudang › Barang Masuk / Barang Keluar / Cutting = SATU pola (bilah Cari → Status ▾ → Jenis ▾ → Gudang ▾ →
//     jumlah → aksi; daftar berbaris; rincian di panel kanan hanya saat dibuka; keadaan daftar = EmptyState).
// M29 Lokasi Rak — kepala satu baris + ?, kartu angka bisa diklik (membuka tab-nya), antrean = tabel berkolom.
// M24 SPK Inspeksi — 9 chip jenis + 7 chip status → dropdown; kartu angka = saringan cepat.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import OutboundScanInterface from "../wms/OutboundScanInterface";
import GoodsReceiptsView from "../wms/grn/GoodsReceiptsView";
import CuttingOpsView from "../wms/CuttingOpsView";
import LocationPutawayView from "../wms/LocationPutawayView";
import InspectionsView from "../inspections/InspectionsView";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
}));
const mockListPage = jest.fn();
jest.mock("../wms/grn/grnApi", () => ({
  __esModule: true,
  grnApi: { listPage: (...a) => mockListPage(...a) },
  errText: () => "gagal",
  STATUS: { draft: { label: "Draf" }, review: { label: "Tinjau SJ" }, counting: { label: "Hitung" }, closed: { label: "Ditutup" } },
}));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, disabled }) => (
    <select data-testid={tid} value={value ?? ""} disabled={disabled} onChange={(e) => onValueChange(e.target.value)}>
      {!options.some((o) => o.value === "") && <option value="" />}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [], loading: false }));
jest.mock("../../hooks/useReceivingMode", () => () => ({ data: { entities: [] }, isGrn: () => false, entityOf: () => null }));
jest.mock("../../hooks/useReceivingUom", () => () => ({ options: null, runPreview: () => {} }));
jest.mock("../wms/inbound/InboundTaskPanel", () => ({
  __esModule: true, default: () => <div data-testid="inbound-panel-stub" />, TaskBadge: ({ status }) => <span>{status}</span>,
}));
jest.mock("../wms/inbound/ScanLabelStatsCard", () => () => null);
jest.mock("../wms/grn/SupplierVariancePanel", () => () => null);
jest.mock("../wms/grn/GrnCreateWizard", () => () => null);
jest.mock("../wms/grn/GrnDetail", () => () => <div data-testid="grn-detail-stub" />);
jest.mock("../wms/LoadingCheckPanel", () => () => null);
jest.mock("../wms/SampleCutPanel", () => () => <div data-testid="sample-cut-stub" />);
jest.mock("../wms/PickListPanel", () => () => null);
jest.mock("../orders/DispatchPaymentGatePanel", () => () => null);
jest.mock("../wms/PendingCutsPanel", () => ({ whId }) => <div data-testid="pending-cuts-stub" data-wh={whId} />);
jest.mock("../wms/PutawayOrdersPanel", () => () => <div data-testid="pa-stub" />);
jest.mock("../wms/location/StructureEditor", () => () => <div data-testid="structure-stub" />);
jest.mock("../wms/location/BinOccupancyGrid", () => () => <div data-testid="bins-stub" />);
jest.mock("../wms/location/OrphanPanel", () => () => <div data-testid="orphans-stub" />);
jest.mock("../wms/location/StockTreePanel", () => () => <div data-testid="stock-stub" />);
jest.mock("../inspections/InspectionFormModal", () => () => null);
jest.mock("../inspections/RandomCheckModal", () => () => null);
jest.mock("../inspections/InspectionDetailPanel", () => () => null);
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn(), notifyError: jest.fn() }));
jest.mock("../../utils/rollLabels", () => ({ printSampleLabel: jest.fn(), printSampleLabels: jest.fn() }));
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const all = (sel) => [...document.body.querySelectorAll(sel)];
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await tick();
  await tick();
  return host;
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset(); mockListPage.mockReset();
});
const pilih = async (el, v) => act(async () => {
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, v);
  el.dispatchEvent(new Event("change", { bubbles: true }));
});
const typeIn = async (el, v) => act(async () => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, v);
  el.dispatchEvent(new Event("input", { bubbles: true }));
});
/** Urutan saringan di bilah daftar (cari/dropdown) menurut DOM. */
const toolbarOrder = (toolbarId) => [...q(toolbarId).querySelectorAll("input[data-testid], select[data-testid]")]
  .map((e) => e.dataset.testid);

// ── M26 · Barang Keluar ───────────────────────────────────────────────────────────────────────────────────────────
const OUT_TASKS = [
  { id: "t1", order_id: "so1", order_number: "KSC/SO-1", status: "created", sku: "SKU1", product_name: "Ceruty",
    warehouse_id: "wh1", warehouse_name: "Gudang Bandung", quantity: 10, picked_qty: 0, unit: "yard", customer_name: "Toko A" },
  { id: "t2", order_id: "so2", order_number: "KSC/SOS-2", status: "packing", task_subtype: "sample_cut", sku: "SKU2",
    warehouse_id: "wh2", warehouse_name: "Gudang Jakarta", quantity: 1, picked_qty: 1, unit: "yard", customer_name: "Toko B",
    cutting_handoff: { received_at: "2026-11-16T10:00:00Z" } },
];

describe("M26 — Barang Keluar memakai pola bilah daftar + panel yang sama", () => {
  beforeEach(() => {
    mockGet.mockImplementation(async (url) => (url.startsWith("/api/outbound/tasks") && !url.includes("/t1/")
      ? { data: OUT_TASKS } : { data: url.includes("saved-views") ? [] : {} }));
  });

  test("chip status & jenis jadi dropdown; urutan Cari → Status → Jenis → Gudang; tanpa panel kosong", async () => {
    await mount(<OutboundScanInterface user={{ permissions: {} }} />);
    expect(all('[data-testid^="filter-status-"]')).toHaveLength(0);
    expect(all('[data-testid^="outbound-kind-"]')).toHaveLength(0);
    expect(toolbarOrder("outbound-filters")).toEqual(["outbound-search", "outbound-status", "outbound-kind", "outbound-wh"]);
    expect(q("outbound-task-count").textContent).toBe("2 tugas");
    expect(document.body.textContent).not.toMatch(/Pilih tugas dari daftar/);
    expect(q("outbound-split").className).not.toMatch(/is-open/);
    await act(async () => { q("outbound-task-t1").click(); });
    expect(q("outbound-split").className).toMatch(/is-open/);
    expect(q("outbound-task-panel")).not.toBeNull();
    await act(async () => { q("outbound-panel-close").click(); });
    expect(q("outbound-task-panel")).toBeNull();
  });

  test("Status ▾ menyaring di server seperti chip lama; Jenis ▾ & Gudang ▾ menyaring daftar", async () => {
    await mount(<OutboundScanInterface user={{ permissions: {} }} />);
    await pilih(q("outbound-status"), "picking");
    await tick();
    expect(mockGet.mock.calls.some(([url]) => url === "/api/outbound/tasks?status=picking")).toBe(true);
    await pilih(q("outbound-status"), "all");
    await tick();
    await pilih(q("outbound-kind"), "sample");
    expect(q("outbound-task-t1")).toBeNull();
    expect(q("outbound-task-t2")).not.toBeNull();
    await pilih(q("outbound-kind"), "all");
    expect([...q("outbound-wh").options].map((o) => o.textContent)).toEqual(["Semua gudang", "Gudang Bandung", "Gudang Jakarta"]);
    await pilih(q("outbound-wh"), "wh1");
    expect(q("outbound-task-t1")).not.toBeNull();
    expect(q("outbound-task-t2")).toBeNull();
  });
});

// ── M26 · Barang Masuk (Kedatangan + Scan Terima per PO) ─────────────────────────────────────────────────────────
const GRNS = [
  { id: "g1", number: "KSC/GRN-1", status: "counting", partner_type: "supplier", partner_name: "PT Benang",
    warehouse_id: "wh1", warehouse_name: "Gudang Bandung", lines: 2, pages: 1, open_blockers: 0, created_at: "2026-11-16T03:00:00Z" },
  { id: "g2", number: "KSC/GRN-2", status: "review", partner_type: "makloon", partner_name: "CV Celup",
    warehouse_id: "wh2", warehouse_name: "Gudang Jakarta", lines: 1, pages: 1, open_blockers: 1, created_at: "2026-11-16T04:00:00Z" },
];

describe("M26 — Barang Masuk: bilah daftar sama, tombol buat di bilah, kartu berpetak → baris", () => {
  const ADMIN = { permissions: { goods_receipt: ["view", "create"], wms: ["view", "update"] } };
  beforeEach(() => {
    mockListPage.mockImplementation(async () => ({ rows: GRNS, res: { headers: { "x-total-count": "2" } } }));
    mockGet.mockImplementation(async (url) => (url === "/api/inbound/tasks" || url.startsWith("/api/inbound/tasks?")
      ? { data: [{ id: "it1", po_id: "po1", po_number: "KSC/PO-9", status: "receiving", sku: "LRK", product_name: "Lurik",
        supplier_name: "PT Benang", warehouse_id: "wh1", warehouse_name: "Gudang Bandung", expected_qty: 10, received_qty: 4, unit: "yard" }] }
      : { data: [] }));
  });

  test("Kedatangan: Cari → Status → Jenis → Gudang; satu tombol 'Kedatangan baru' di ujung bilah", async () => {
    await mount(<GoodsReceiptsView currentUser={ADMIN} selectedEntity="all" />);
    expect(all('[data-testid^="grn-filter-"]').map((e) => e.dataset.testid)).toEqual(["grn-filter-bar"]);   // tanpa chip
    expect(toolbarOrder("grn-filter-bar")).toEqual(["grn-search", "grn-status", "grn-kind", "grn-wh"]);
    expect(q("grn-filter-bar").contains(q("grn-new-button"))).toBe(true);
    expect(all("button").filter((b) => /Kedatangan baru/.test(b.textContent))).toHaveLength(1);
    expect(q("grn-list").contains(q("grn-card-g1"))).toBe(true);
    expect(q("grn-count").textContent).toBe("2 kedatangan");
  });

  test("Status ▾ memakai nilai chip lama (server); Jenis ▾ & Gudang ▾ menyaring kedatangan termuat", async () => {
    await mount(<GoodsReceiptsView currentUser={ADMIN} selectedEntity="all" />);
    expect([...q("grn-status").options].map((o) => o.value))
      .toEqual(["", "draft,review", "counting", "reconcile,closing", "closed", "rejected,cancelled"]);
    await pilih(q("grn-status"), "draft,review");
    await tick();
    expect(mockListPage).toHaveBeenLastCalledWith({ status: "draft,review", q: "" });
    await pilih(q("grn-kind"), "makloon");
    expect(q("grn-card-g1")).toBeNull();
    expect(q("grn-card-g2")).not.toBeNull();
    expect(q("grn-count").textContent).toBe("1 kedatangan");
    await pilih(q("grn-kind"), "");
    await pilih(q("grn-wh"), "wh1");
    expect(q("grn-card-g1")).not.toBeNull();
    expect(q("grn-card-g2")).toBeNull();
    await act(async () => { q("grn-card-g1").click(); });
    expect(q("grn-detail-stub")).not.toBeNull();   // rincian kedatangan = halaman sendiri (templat C)
  });

  test("Scan Terima per PO: bilah sama (Cari → Status → Gudang), panel hanya saat tugas dibuka", async () => {
    await mount(<GoodsReceiptsView currentUser={ADMIN} selectedEntity="all" />);
    await act(async () => { q("grn-view-tab-legacy").click(); });
    await tick();
    expect(all('[data-testid^="filter-status-"]')).toHaveLength(0);
    expect(toolbarOrder("inbound-filters")).toEqual(["inbound-search", "inbound-status", "inbound-wh"]);
    expect(q("inbound-task-count").textContent).toBe("1 tugas");
    expect(document.body.textContent).not.toMatch(/Pilih tugas dari daftar/);
    expect(q("inbound-panel-stub")).toBeNull();
    await act(async () => { q("inbound-task-it1").click(); });
    expect(q("inbound-split").className).toMatch(/is-open/);
    expect(q("inbound-panel-stub")).not.toBeNull();
    await pilih(q("inbound-status"), "qc_check");
    await tick();
    expect(mockGet.mock.calls.some(([url]) => url === "/api/inbound/tasks?status=qc_check")).toBe(true);
    await typeIn(q("inbound-search"), "tidak-ada");
    expect(q("inbound-list-state")).not.toBeNull();
  });
});

// ── M26 · Cutting ────────────────────────────────────────────────────────────────────────────────────────────────
const CUT_TASKS = [
  { id: "c1", task_subtype: "sample_cut", status: "created", picked_qty: 0, order_id: "so5", order_number: "KSC/SOS-5",
    customer_name: "Toko Uji", warehouse_id: "wh1", warehouse_name: "Gudang Bandung", product_name: "Katun", quantity: 1, unit: "yard" },
  { id: "c2", task_subtype: "sample_cut", status: "created", picked_qty: 0, order_id: "so5", order_number: "KSC/SOS-5",
    customer_name: "Toko Uji", warehouse_id: "wh1", warehouse_name: "Gudang Bandung", product_name: "Rayon", quantity: 1, unit: "yard" },
];

describe("M26 — Cutting: chip tahap → dropdown, satu Gudang ▾, paket dibuka di panel", () => {
  beforeEach(() => {
    mockGet.mockImplementation(async (url) => (url === "/api/outbound/tasks" ? { data: CUT_TASKS }
      : url === "/api/warehouses" ? { data: [{ id: "wh1", name: "Gudang Bandung" }, { id: "wh2", name: "Gudang Jakarta" }] }
        : { data: [] }));
  });

  test("bilah Cari → Tahap → Jenis → Gudang; satu dropdown gudang untuk paket & potong roll SO", async () => {
    await mount(<CuttingOpsView />);
    expect(all('[data-testid^="cutting-ops-stage-"]')).toHaveLength(0);
    expect(toolbarOrder("cutting-ops-toolbar")).toEqual(["cutting-ops-search", "cutting-ops-stage", "cutting-ops-kind", "cutting-ops-wh"]);
    expect(q("cutting-ops-cut-wh")).toBeNull();
    expect(q("cutting-ops-count").textContent).toBe("1 paket");
    await pilih(q("cutting-ops-wh"), "wh2");
    expect(q("pending-cuts-stub").dataset.wh).toBe("wh2");
    expect(q("cutting-ops-empty")).not.toBeNull();   // saringan tanpa hasil = EmptyState baku
    await pilih(q("cutting-ops-kind"), "so");
    expect(q("cutting-ops-list")).toBeNull();
    expect(q("cutting-ops-search")).toBeNull();
    expect(q("pending-cuts-stub")).not.toBeNull();
    await pilih(q("cutting-ops-kind"), "sample");
    expect(q("pending-cuts-stub")).toBeNull();
  });

  test("klik paket → panel rincian berisi baris potong (tanpa tombol Rincian/Tutup)", async () => {
    await mount(<CuttingOpsView />);
    expect(q("cutting-line-c1")).toBeNull();
    expect(all("button").some((b) => b.textContent === "Rincian")).toBe(false);
    await act(async () => { q("cutting-open-so5").click(); });
    expect(q("cutting-ops-split").className).toMatch(/is-open/);
    expect(q("cutting-detail-so5")).not.toBeNull();
    expect(q("cutting-line-c1")).not.toBeNull();
    expect(q("cutting-detail-cut-all-so5").textContent).toMatch(/Potong semua \(2\)/);
    await act(async () => { q("cutting-line-manual-c2").click(); });
    expect(q("sample-cut-stub")).not.toBeNull();
    await act(async () => { q("cutting-detail-close").click(); });
    expect(q("cutting-detail-so5")).toBeNull();
  });
});

// ── M29 · Lokasi Rak ─────────────────────────────────────────────────────────────────────────────────────────────
describe("M29 — Lokasi Rak: kepala satu baris, kartu angka bisa diklik, antrean berbentuk tabel", () => {
  beforeEach(() => {
    mockGet.mockImplementation(async (url) => {
      if (url === "/api/wms/my-location-scope") return { data: {} };
      if (url === "/api/warehouses") return { data: [{ id: "wh1", name: "Gudang Utama", status: "active" }] };
      if (url === "/api/warehouses/wh1/locations") return { data: { warehouse: { name: "Gudang Utama" }, zones: [], bins: [],
        bin_count: 1, bins_without_capacity: 1, binned_rolls: 0, unassigned: { rolls: 2 }, orphan: { rolls: 0 } } };
      if (url === "/api/inventory/putaway/queue") return { data: { rolls: [
        { id: "r1", roll_no: "RL-1", sku: "KNT-1", product_name: "Chikita", length_remaining: 26, unit: "kg", ready: true },
        { id: "r2", roll_no: "RL-2", sku: "KNT-1", product_name: "Chikita", length_remaining: 25, unit: "kg", ready: false,
          blocked_reason: "Ada reservasi potong" }], total: 2, skip: 0, limit: 100, truncated: false } };
      return { data: [] };
    });
  });

  test("tanpa baris hierarki & paragraf; empat kartu angka = pintasan tab; antrean = tabel berkolom", async () => {
    await mount(<LocationPutawayView currentUser={{ permissions: {} }} selectedEntity="all" />);
    expect(q("lp-hierarchy")).toBeNull();
    expect(document.body.textContent).not.toMatch(/Saran bin hanya menampilkan bin/);   // pindah ke ?
    const cards = all('[data-testid="lp-kpis"] > button');
    expect(cards).toHaveLength(4);
    expect(q("lp-unassigned").getAttribute("aria-pressed")).toBe("true");   // tab Penempatan aktif
    expect(q("lp-queue-head").textContent).toMatch(/Roll.*Barang.*Bin tujuan.*Aksi/);
    expect(q("lp-queue-table").contains(q("lp-queue-r1"))).toBe(true);
    expect(q("lp-queue-blocked-r2").textContent).toMatch(/Terhambat: Ada reservasi potong/);
    expect(q("lp-queue-count").textContent).toMatch(/Roll 1–2 dari 2 belum ditempatkan/);
    await act(async () => { q("lp-kpi-bins").click(); });
    expect(q("bins-stub")).not.toBeNull();
    expect(q("lp-kpi-bins").getAttribute("aria-pressed")).toBe("true");
    expect(q("lp-kpi-bins").textContent).toMatch(/1 tanpa kapasitas/);   // Kapasitas digabung ke kartu Bin
    await act(async () => { q("lp-kpi-orphan").click(); });
    expect(q("orphans-stub")).not.toBeNull();
  });
});

// ── M24 · SPK Inspeksi ───────────────────────────────────────────────────────────────────────────────────────────
describe("M24 — SPK Inspeksi: chip jenis & status → dropdown, kartu angka = saringan cepat", () => {
  const listCalls = () => mockGet.mock.calls.filter(([url]) => url === "/api/inspections").map(([, cfg]) => cfg?.params || {});
  beforeEach(() => {
    mockGet.mockImplementation(async (url) => (url.includes("meta")
      ? { data: { kinds: [{ value: "po_receipt", label: "Penerimaan PO" }, { value: "random_check", label: "Random Check" }], policy: {} } }
      : url === "/api/inspections" ? { data: { items: [], total: 0, stats: { total: 4, draft: 1, in_progress: 2, hold: 1 } } }
        : { data: [] }));
  });

  test("tanpa chip; bilah Cari → Status → Jenis; status/jenis dikirim ke server", async () => {
    await mount(<InspectionsView currentUser={{ role: "manager", permissions: { inspection: ["create"] } }} />);
    expect(all('[data-testid^="ins-chip-"]')).toHaveLength(0);
    expect(toolbarOrder("ins-filters")).toEqual(["ins-search", "ins-status-filter", "ins-kind-filter"]);
    expect(q("ins-filters").contains(q("ins-create-button"))).toBe(true);
    expect(q("ins-policy-note")).toBeNull();   // kebijakan di ? kepala, bukan paragraf permanen
    expect([...q("ins-kind-filter").options].map((o) => o.textContent)).toEqual(["Semua jenis", "Penerimaan PO", "Random Check"]);
    await pilih(q("ins-kind-filter"), "random_check");
    await pilih(q("ins-status-filter"), "assigned");
    await tick();
    expect(listCalls().some((p) => p.kind === "random_check" && p.status === "assigned")).toBe(true);
  });

  test("kartu angka: Belum ditugaskan → status draft; Barang DITAHAN → hold_only (klik lagi = lepas)", async () => {
    await mount(<InspectionsView currentUser={{ role: "manager", permissions: {} }} />);
    expect(all('[data-testid="ins-kpis"] > button')).toHaveLength(4);
    await act(async () => { q("ins-kpi-draft").click(); });
    await tick();
    expect(q("ins-kpi-draft").getAttribute("aria-pressed")).toBe("true");
    expect(q("ins-status-filter").value).toBe("draft");
    await act(async () => { q("ins-kpi-hold").click(); });
    await tick();
    expect(listCalls().some((p) => p.hold_only === true && p.status === "draft")).toBe(true);
    await act(async () => { q("ins-kpi-total").click(); });
    expect(q("ins-status-filter").value).toBe("");
    expect(q("ins-kpi-hold").getAttribute("aria-pressed")).toBe("false");
  });
});

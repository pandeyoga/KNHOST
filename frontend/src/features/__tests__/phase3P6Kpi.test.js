// Fase 3 · P6 — D-08 (satu rapor desainer: KPI Desainer tab "Pekerjaan DSR" untuk tim, Profil Saya › KPI Saya
// untuk diri sendiri; Permintaan Desain hanya kartu tautan), L-01 (PageTabs/FilterChips di Permintaan Desain),
// L-03 SDM (form Karyawan = FormModal bernomor; isian cuti ESS = isian HRD) dan API P7 (form DSR mandiri).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import DesignerKpiView from "../designer/DesignerKpiView";
import DesignRequestsView from "../design/DesignRequestsView";
import DesignRequestCreateModal from "../design/DesignRequestCreateModal";
import MyDesignerKpiSection, { showMyDesignerKpi, showMyDsrReport } from "../hr/MyDesignerKpiSection";
import { EmployeeFormDrawer } from "../hr/EmployeeFormDrawer";
import { MyLeaveCard } from "../hr/MyLeaveCard";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";

const mockGet = jest.fn();
const mockDesignerReport = jest.fn();
const mockMyReport = jest.fn();
const mockDsrMeta = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: { get: (...a) => mockGet(...a), post: jest.fn(() => Promise.resolve({ data: {} })), patch: jest.fn(() => Promise.resolve({ data: {} })), defaults: { headers: { common: {} } } },
}));
jest.mock("../designer/designerApi", () => ({
  designerKpi: () => Promise.resolve({ items: [], summary: {} }),
  slaBoard: () => Promise.resolve({ items: [] }),
  myDesignerKpi: () => Promise.resolve({ me: null, rounds: [] }),
  downloadDesignerKpi: jest.fn(), downloadDesignerReport: jest.fn(), runSlaEscalation: jest.fn(), saveBlob: jest.fn(),
  designerKpiTrend: () => Promise.resolve({ items: [] }), designScoreTrend: () => Promise.resolve({ items: [] }),
}));
jest.mock("../design/designRequestsApi", () => {
  const actual = jest.requireActual("../design/designRequestsApi");
  return {
    ...actual,
    designerReport: (...a) => mockDesignerReport(...a),
    myDesignerReport: (...a) => mockMyReport(...a),
    dsrMeta: (...a) => mockDsrMeta(...a),
  };
});
jest.mock("../../hooks/useDomainEnums", () => ({
  __esModule: true, default: () => ({ options: () => [], labelOf: (k, v) => v || "—", loading: false }),
}));
jest.mock("../designer/DesignerKpiTrendChart", () => () => null);
jest.mock("../designer/DesignScoreTrendChart", () => () => null);
jest.mock("../../components/LocationFields", () => () => <div data-testid="employee-loc" />);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
}
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  [mockGet, mockDesignerReport, mockMyReport, mockDsrMeta].forEach((m) => m.mockReset());
  document.body.innerHTML = "";
});
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); };
const withNav = (role, preset, child, onNavigateTo = () => {}) => (
  <AppNavProvider role={role} onNavigateTo={onNavigateTo} onOpenDocument={() => {}}>
    <ViewPresetProvider preset={preset}>{child}</ViewPresetProvider>
  </AppNavProvider>
);
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}

test("D-08: KPI Desainer — PageTabs Skor & SLA | Pekerjaan DSR; preset {tab:'dsr'} membuka rapor DSR", async () => {
  mockDesignerReport.mockResolvedValue({ items: [{ designer_id: "u1", designer: "Dina", assigned: 3, acc_rate_pct: 50 }], totals: { requests: 3 } });
  await mount(withNav("manager", { view: "designer-kpi", nonce: 1, tab: "dsr" },
    <DesignerKpiView currentUser={{ role: "manager" }} selectedEntity="ent_ksc" />));
  expect(q("designer-kpi-tab-dsr").getAttribute("aria-selected")).toBe("true");
  expect(q("designer-report-panel")).toBeTruthy();
  expect(q("dsr-report-row-u1")).toBeTruthy();
  expect(q("designer-kpi-summary")).toBeNull();
  await click(q("designer-kpi-tab-score"));
  expect(q("designer-report-panel")).toBeNull();
  expect(q("designer-kpi-summary")).toBeTruthy();
  // L-03 — modal rapor PDF bukan lagi lapisan fixed buatan sendiri
  expect(document.body.querySelector(".fixed.inset-0.z-50")).toBeNull();
});

const DSR_LIST = { items: [{ id: "dsr1", number: "KSC/DSR-1", status: "submitted", status_label: "Diajukan", brief: "Motif bunga" }], total: 1, page: 1, page_size: 50, has_more: false, summary: { total: 1, by_status: { submitted: 1 } } };

test("D-08: Permintaan Desain (admin) — tanpa tab rapor; kartu tautan → KPI Desainer tab DSR; Papan/Daftar = PageTabs", async () => {
  routeGet({ "/design-requests/meta": { role: "admin", own_only: false, designers: [], sources: [] }, "/design-requests": DSR_LIST, "/sales-orders": [] });
  mockDsrMeta.mockResolvedValue({ role: "admin", own_only: false, designers: [], sources: [] });
  const nav = jest.fn();
  await mount(withNav("admin", null, <DesignRequestsView currentUser={{ role: "admin" }} selectedEntity="ent_ksc" />, nav));
  expect(q("dsr-tab-report")).toBeNull();
  expect(q("dsr-tab-myreport")).toBeNull();
  expect(q("dsr-tab-board").getAttribute("role")).toBe("tab");
  expect(q("dsr-chip-all").getAttribute("aria-pressed")).toBe("true");
  await click(q("dsr-report-link-open"));
  expect(nav).toHaveBeenCalledWith("designer-kpi", expect.objectContaining({ preset: { tab: "dsr" } }));
  expect(q("dsr-myreport-link")).toBeNull();
  await click(q("dsr-tab-list"));
  expect(q("dsr-row-dsr1")).toBeTruthy();
});

test("D-08: Permintaan Desain (desainer) — kartu 'Rapor Saya' → Profil Saya {section:'kpi', tab:'dsr'}", async () => {
  routeGet({ "/design-requests/meta": { role: "designer", own_only: true, designers: [] }, "/design-requests": DSR_LIST });
  mockDsrMeta.mockResolvedValue({ role: "designer", own_only: true, designers: [] });
  const nav = jest.fn();
  await mount(withNav("designer", null, <DesignRequestsView currentUser={{ role: "designer" }} selectedEntity="ent_ksc" />, nav));
  expect(q("dsr-report-link")).toBeNull();
  await click(q("dsr-myreport-link-open"));
  expect(nav).toHaveBeenCalledWith("hr-my-profile", expect.objectContaining({ preset: { section: "kpi", tab: "dsr" } }));
});

test("D-08: Profil Saya › KPI Saya — satu kartu bertab; preset tab DSR → rapor milik sendiri", async () => {
  expect(showMyDesignerKpi({ role: "designer" })).toBe(true);
  expect(showMyDesignerKpi({ role: "manager", permissions: {} })).toBe(false);
  expect(showMyDsrReport({ role: "designer" })).toBe(true);
  expect(showMyDsrReport({ role: "md", permissions: { design_request: ["deliver"] } })).toBe(false);
  mockMyReport.mockResolvedValue({ me: { avg_days: 2, acc_rate_pct: 80 }, totals: { requests: 4 }, team: {} });
  await mount(withNav("designer", { view: "hr-my-profile", nonce: 3, section: "kpi", tab: "dsr" },
    <MyDesignerKpiSection currentUser={{ role: "designer" }} />));
  expect(q("ess-kpi-tab-dsr").getAttribute("aria-selected")).toBe("true");
  expect(q("my-designer-report-panel")).toBeTruthy();
  expect(q("dsr-myreport-total").textContent).toBe("4");
  await click(q("ess-kpi-tab-rnd"));
  expect(q("my-designer-report-panel")).toBeNull();
});

test("D-08: MD (bukan penerima tugas DSR) hanya melihat tab ronde sample R&D", async () => {
  await mount(withNav("md", null, <MyDesignerKpiSection currentUser={{ role: "md", permissions: {} }} />));
  expect(q("ess-kpi-tab-rnd")).toBeTruthy();
  expect(q("ess-kpi-tab-dsr")).toBeNull();
});

test("API P7: form Permintaan Desain mandiri — memuat meta sendiri; sumber pelanggan punya pemilih pelanggan", async () => {
  mockDsrMeta.mockResolvedValue({ designers: [], sources: [{ id: "customer", label: "Permintaan pelanggan" }], categories: { pattern: [], design: [] } });
  routeGet({ "/customers": [{ id: "c1", name: "PT Bima" }] });
  await mount(<DesignRequestCreateModal open onClose={() => {}} onCreated={() => {}} prefill={{ source: "customer" }} />);
  expect(mockDsrMeta).toHaveBeenCalledTimes(1);
  expect(q("dsr-create-modal").getAttribute("role")).toBe("dialog");
  expect(q("dsr-customer-select")).toBeTruthy();
  expect(mockGet.mock.calls.some(([u]) => u.includes("/customers"))).toBe(true);
});

test("L-03/L-10: form Karyawan = FormModal (bukan Sheet) dengan 4 bagian bernomor; Simpan nonaktif tanpa nama", async () => {
  routeGet({});
  await mount(<EmployeeFormDrawer open onClose={() => {}} onSaved={() => {}} departments={[]} positions={[]} entities={[]} users={[]} />);
  expect(q("employee-form-drawer").getAttribute("role")).toBe("dialog");
  ["employee-sec-1", "employee-sec-2", "employee-sec-3", "employee-sec-4"].forEach((id) => expect(q(id)).toBeTruthy());
  expect(q("employee-name-input")).toBeTruthy();
  expect(q("employee-npwp-input")).toBeTruthy();
  expect(q("employee-salary-input")).toBeTruthy();
  expect(q("employee-save-button").disabled).toBe(true);
});

test("L-03: ESS cuti — isian = komponen HRD (tipe/dari/sampai/alasan), pilihan Cuti/Lembur = PageTabs", async () => {
  routeGet({ "/hr/leave-requests/me": { balance: { remaining: 10, entitlement: 12, used: 2, pending: 0 }, requests: [] }, "/hr/overtime/me": { requests: [] } });
  await mount(<MyLeaveCard />);
  await click(q("ess-leave-request-button"));
  expect(q("ess-leave-modal").getAttribute("role")).toBe("dialog");
  ["ess-leave-type", "ess-leave-from", "ess-leave-to", "ess-leave-reason"].forEach((id) => expect(q(id)).toBeTruthy());
  expect(q("ess-leave-modal-tab-cuti").getAttribute("role")).toBe("tab");
  await click(q("ess-leave-modal-tab-lembur"));
  expect(q("ess-ot-hours")).toBeTruthy();
  expect(q("ess-leave-type")).toBeNull();
});

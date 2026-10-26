// Fase 4 · R4 — pop-up & tata letak R&D, desain, SDM, marketing, katalog, retur.
// L-03: pop-up buatan sendiri → FormModal/DetailModal/MediaLightbox (galat di dalam pop-up) · L-02: PageHeader ·
// L-06: kolom prioritas + pemilih Kolom + Rincian (designer-kpi), tabel roll retur tanpa min-width ·
// L-07: `.data-table` (KPI, Presensi) · L-08: "Saring (n)" + panel lipat, nol netral · L-10: Induk produk bernomor ·
// grid HP: `grid-cols-1` sebelum `<bp>:grid-cols-…` di himpunan berkas R4.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import DesignFormModal from "../rnd/DesignFormModal";
import SampleProofGallery from "../rnd/SampleProofGallery";
import ReturnQuarantinePanel from "../sales/ReturnQuarantinePanel";
import ReturnRollsPanel from "../sales/ReturnRollsPanel";
import DesignerKpiTable from "../designer/DesignerKpiTable";
import DesignerKpiView from "../designer/DesignerKpiView";
import KpiView from "../hr/KpiView";
import AttendanceView from "../hr/AttendanceView";
import LeaveView from "../hr/LeaveView";
import SocialAccounts from "../marketing/SocialAccounts";
import ContentCalendar from "../marketing/ContentCalendar";
import { FamilyForm, axesSummary } from "../catalog/FamilyForm";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: jest.fn(() => Promise.resolve({ data: {} })),
    delete: jest.fn(), defaults: { headers: { common: {} } } },
}));
jest.mock("../../components/KNSelect", () => {
  const S = (props) => (
    <select data-testid={props["data-testid"]} value={props.value} onChange={(e) => props.onValueChange(e.target.value)}>
      {(props.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../rnd/rndApi", () => ({
  studioCategories: () => Promise.resolve([{ code: "SLR", name: "Salur", id: "c1", status: "active" }]),
  studioNextCode: () => Promise.resolve({ code: "ADM-SLR-AO-001", pattern: "x", designer_code: "ADM", parts: {} }),
  createDesign: jest.fn(() => Promise.resolve({ id: "d1" })),
  patchDesign: jest.fn(() => Promise.resolve({ id: "d1" })),
  createCategory: jest.fn(() => Promise.resolve({})),
  patchCategory: jest.fn(() => Promise.resolve({})),
  studioTags: () => Promise.resolve([]),
  roundProofUrl: (sid, rid, aid) => `/api/rnd/samples/${sid}/rounds/${rid}/attachments/${aid}`,
}));
jest.mock("../designer/designerApi", () => ({
  designerKpi: () => Promise.resolve({ items: [], summary: { designers: 0, rounds: 0, overdue_now: 0 }, divisions_present: [{ id: "dv1", name: "Divisi A" }] }),
  slaBoard: () => Promise.resolve({ items: [] }),
  downloadDesignerKpi: jest.fn(), downloadDesignerReport: jest.fn(), runSlaEscalation: jest.fn(), saveBlob: jest.fn(),
  designerKpiTrend: () => Promise.resolve({ items: [] }), designScoreTrend: () => Promise.resolve({ items: [] }),
}));
jest.mock("../designer/DesignerKpiTrendChart", () => () => null);
jest.mock("../designer/DesignScoreTrendChart", () => () => null);
jest.mock("../../components/MediaLightbox", () => (props) => (
  <div role="dialog" data-testid={props.testId} data-index={props.index}>{props.items.map((i) => i.caption).join(" | ")}</div>
));
jest.mock("../rnd/ProofImage", () => ({ __esModule: true, default: () => <span />, isImageProof: () => true }));
jest.mock("../../hooks/useDomainEnums", () => ({
  __esModule: true,
  default: () => ({ options: () => [{ value: "A", label: "A" }], labelOf: (k, v) => v || "—", fieldRules: () => ({ required: [] }), fieldLabels: {}, loading: false }),
}));
jest.mock("../../hooks/useCatalogMasters", () => ({
  __esModule: true, default: () => ({ categoryOptions: [{ value: "KAT", label: "KAT" }], motifOptions: [{ value: "Polos", label: "Polos" }], unitOptions: [{ value: "meter", label: "meter" }] }),
}));
jest.mock("../../components/BaseFabricPicker", () => () => null);

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
beforeEach(() => { mockGet.mockImplementation(() => Promise.resolve({ data: [] })); });
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
  try { window.localStorage.clear(); } catch { /* noop */ }
});
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); };
const change = async (el, v) => { await act(async () => { el.value = v; el.dispatchEvent(new Event("change", { bubbles: true })); }); };
const setInput = async (el, v) => {
  const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => { setter.call(el, v); el.dispatchEvent(new Event("input", { bubbles: true })); });
};
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}

test("L-03: Desain Baru = FormModal (galat di kaki pop-up); master kategori = pop-up saudara ber-PageTabs, aksen biru", async () => {
  await mount(<DesignFormModal mode="create" canManageMaster onClose={() => {}} onSaved={() => {}} />);
  const dlg = q("design-form-modal");
  expect(dlg.getAttribute("role")).toBe("dialog");
  expect(q("design-form-modal-overlay")).toBeTruthy();                       // lapisan baku FormModal
  await click(q("design-form-save"));
  expect(q("design-form-modal-error").textContent).toMatch(/Judul desain wajib/);
  expect(dlg.contains(q("design-form-modal-error"))).toBe(true);            // galat DI DALAM pop-up
  expect(q("design-manage-categories-pattern").className).toContain("#0058CC");
  await click(q("design-manage-categories-pattern"));
  const cat = q("category-manager-modal");
  expect(cat.getAttribute("role")).toBe("dialog");
  expect(dlg.contains(cat)).toBe(false);                                     // saudara, bukan bersarang di kartu
  expect(q("category-type-pattern").getAttribute("role")).toBe("tab");
  expect(q("category-type-pattern").getAttribute("aria-selected")).toBe("true");
  expect(document.body.innerHTML).not.toContain("6B219A");
});

test("L-03: galeri bukti sample memakai MediaLightbox bersama (keterangan supplier · round · hasil)", async () => {
  const sample = {
    id: "s1", participants: [{ supplier_id: "sp1", supplier_name: "Mitra Tenun" }],
    rounds: [{ id: "r1", supplier_id: "sp1", round_no: 2, result: "", score: 86, type_code: "labdip",
      attachments: [{ id: "a1", filename: "bukti.jpg", content_type: "image/jpeg" }] }],
  };
  await mount(<SampleProofGallery sample={sample} code="labdip" />);
  expect(q("sample-proof-lightbox")).toBeNull();
  await click(q("sample-proof-thumb-a1"));
  const lb = q("sample-proof-lightbox");
  expect(lb.textContent).toMatch(/Mitra Tenun · Round 2 · .*skor 86/);
  expect(document.body.querySelector(".fixed.inset-0")).toBeNull();          // tidak ada lapisan buatan sendiri
});

test("L-03: Transfer Kepemilikan roll retur = FormModal; galat server tampil DI DALAM pop-up", async () => {
  routeGet({
    "/quarantine": [{ id: "r1", roll_no: "RL-1", status: "available", owner_entity_id: "e1", owner_entity_name: "KSC", warehouse_name: "G1", length: 10, grade: "A" }],
    "/entities": [{ id: "e1", short_name: "KSC" }, { id: "e2", short_name: "KN" }],
    "/suppliers": [],
  });
  mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Periode akuntansi terkunci." } } });
  await mount(<ReturnQuarantinePanel ret={{ id: "sret_1" }} canApprove onReleased={() => {}} />);
  await click(q("transfer-ownership-r1"));
  const dlg = q("transfer-ownership-modal");
  expect(dlg.getAttribute("role")).toBe("dialog");
  await click(q("confirm-transfer-ownership-btn"));
  await act(async () => {});
  expect(q("transfer-ownership-modal-error").textContent).toMatch(/Periode akuntansi terkunci/);
  expect(dlg.contains(q("transfer-ownership-modal-error"))).toBe(true);
  expect(document.body.querySelector(".modal-card")).toBeNull();
  // tabel 8 kolom bergulir di dalam kartu (tidak melebarkan halaman HP)
  expect(q("quarantine-roll-r1").closest(".overflow-x-auto")).toBeTruthy();
});

test("L-06: tabel roll retur — .data-table tanpa min-width 760; kondisi + checklist satu kolom", async () => {
  const ret = { id: "sret_1", attachments: [] };
  const item = { product_id: "p1", product_name: "Kain A", quantity_returned: 30, unit: "yard", condition: "ok", reason: "noda",
    roll_ids: ["r1"], roll_qtys: { r1: 10 }, roll_nos: { r1: "RL-1" }, roll_details: { r1: { condition: "minor", hangtag_missing: true } } };
  await mount(<ReturnRollsPanel ret={ret} items={[item]} fullView canDecide={false} />);
  const row = q("return-roll-r1");
  const table = row.closest("table");
  expect(table.className).toContain("data-table");
  expect(table.style.minWidth).toBe("");
  expect(row.textContent).toMatch(/Cacat ringan.*Hangtag hilang/);
  expect(table.querySelectorAll("thead th").length).toBe(6);                 // dulu 7 kolom
});

const KPI_ROW = { designer: "dina", designer_key: "dina", rank: 1, rounds: 3, acc: 1, revisi: 1, tolak: 1, late_total: 2, overdue_now: 1,
  on_time_pct: 66.7, rework_pct: 50, avg_score: 80, avg_days: 2.5, design_versions: 4, designs: 2, design_avg_score: 1.5,
  design_acc: 2, design_revisions: 1, grade_score: 82.5, grade_letter: "B", grade_base: 85, grade_penalty: 2.5, grade_meaning: "Baik" };

test("L-06: KPI Desainer — kolom prioritas, pemilih Kolom (diingat) & Rincian berisi SEMUA angka", async () => {
  await mount(<DesignerKpiTable items={[KPI_ROW]} onSelect={() => {}} selected="" onDownloadReport={() => {}} />);
  expect(q("designer-kpi-row-dina").closest("table").className).toContain("data-table");
  expect(q("designer-kpi-sort-grade_score")).toBeTruthy();
  expect(q("designer-kpi-sort-acc")).toBeNull();                              // kolom tambahan tersembunyi bawaan
  expect(q("designer-kpi-report-dina")).toBeTruthy();                         // Rapor PDF tetap di baris
  await click(q("designer-kpi-columns-toggle"));
  await click(q("designer-kpi-col-acc"));
  expect(q("designer-kpi-sort-acc")).toBeTruthy();
  expect(JSON.parse(window.localStorage.getItem("kn.designer-kpi.cols"))).toEqual(["acc"]);
  await click(q("designer-kpi-detail-dina"));
  const dlg = q("designer-kpi-detail");
  expect(dlg.getAttribute("role")).toBe("dialog");
  expect(q("designer-kpi-detail-val-late_total").textContent).toMatch(/2.*1 nunggak/);
  expect(q("designer-kpi-detail-val-design_revisions").textContent).toBe("1");
  expect(dlg.querySelectorAll("[data-testid^='designer-kpi-detail-val-']").length).toBe(14);   // 15 kolom − nama (divisi tak ada)
});

test("L-08: KPI Desainer — bilah alat ringkas: Saring (n) membuka panel periode & divisi; MetricRow nol netral", async () => {
  await mount(<DesignerKpiView currentUser={{ role: "manager" }} selectedEntity="ent_ksc" />);
  expect(q("designer-kpi-period")).toBeNull();                                // saringan terlipat bawaan
  expect(q("designer-kpi-filter-toggle").textContent).toBe(" Saring");
  await click(q("designer-kpi-filter-toggle"));
  expect(q("designer-kpi-filters")).toBeTruthy();
  await change(q("designer-kpi-division"), "dv1");
  expect(q("designer-kpi-filter-toggle").textContent).toMatch(/Saring \(1\)/);
  await change(q("designer-kpi-period"), "90d");
  expect(q("designer-kpi-filter-toggle").textContent).toMatch(/Saring \(2\)/);
  await click(q("designer-kpi-filter-reset"));
  expect(q("designer-kpi-filter-toggle").textContent).not.toMatch(/\(/);
  const zero = q("designer-kpi-summary").querySelectorAll(".metric-zero");
  expect(zero.length).toBeGreaterThan(0);                                     // "Nunggak lewat tenggat 0" netral
  expect(q("designer-kpi-export-xlsx").closest("[role=group]")).toBeTruthy();  // Excel/PDF/CSV satu grup "Unduh"
});

test("L-07/L-08: KPI Karyawan & Presensi — .data-table (ResponsiveTable) + MetricRow; tabel grid min-w hilang", async () => {
  const perms = { hr: ["manage_attendance"] };
  routeGet({ "/hr/kpi": [{ id: "k1", employee_name: "Ayu", period: "2026-10", metric: "Desain baru", target: 10, actual: 9, score: 90, weight: 1 }], "/hr/employees": [] });
  await mount(<KpiView currentUser={{ role: "admin", permissions: perms }} selectedEntity="all" />);
  const row = q("kpi-row-k1");
  expect(row.closest("table").className).toContain("data-table");
  expect(q("kpi-edit-k1-button")).toBeTruthy();
  expect(q("kpi-recap")).toBeTruthy();
  await act(async () => { root.unmount(); }); root = null;
  routeGet({ "/hr/attendance": { items: [{ id: "a1", employee_name: "Budi", status: "flagged", clock_in: "2026-10-26T08:05:00", late_min: 5, work_min: 0, method: "geo" }], total: 1 }, "/hr/employees": [] });
  await mount(<AttendanceView currentUser={{ role: "admin", permissions: perms }} selectedEntity="all" />);
  const arow = q("attendance-row-a1");
  expect(arow.closest("table").className).toContain("data-table");
  expect(q("approve-attendance-a1")).toBeTruthy();
  expect(document.body.querySelector("[class*='min-w-[920px]']")).toBeNull();
  expect(q("attendance-stats").querySelectorAll(".metric-card").length).toBe(4);
});

test("L-08: Saldo Cuti — Terpakai bukan merah, nol netral; tab = PageTabs (testid lama tetap)", async () => {
  routeGet({ "/hr/leave-balances": [{ id: "b1", employee_id: "e1", entitlement: 12, used: 2, pending: 0, remaining: 0 }], "/hr/employees": [{ id: "e1", name: "Ayu" }] });
  await mount(<LeaveView currentUser={{ role: "admin", permissions: { hr: ["manage_attendance"] } }} selectedEntity="all" />);
  expect(q("leave-tab-balance").getAttribute("role")).toBe("tab");
  await click(q("leave-tab-balance"));
  await act(async () => {});
  expect(q("leave-balance-used-e1").className).not.toContain("C0392B");
  expect(q("leave-balance-pending-e1").className).toContain("9A9BA3");
  expect(q("leave-balance-remaining-e1").className).toContain("9A9BA3");    // sisa 0 tidak hijau
});

test("L-02/L-08: Akun Sosmed ber-PageHeader + section-card; Kalender Konten: Saring (n) + PageTabs tampilan", async () => {
  routeGet({ "/marketing/accounts": [{ id: "ac1", entity_name: "KSC", platform: "instagram", handle: "ksc", active: true, posts_total: 2 }], "/marketing/meta": { active_entity_name: "KSC" } });
  const perms = { marketing: ["create", "update"] };
  await mount(<SocialAccounts currentUser={{ permissions: perms }} selectedEntity="all" />);
  expect(q("mkt-accounts-head").querySelector("h1.view-title").textContent).toMatch(/Akun Sosmed/);
  expect(q("mkt-new-account").closest("[data-testid='mkt-accounts-head']")).toBeTruthy();
  expect(q("mkt-account-ac1").closest(".section-card")).toBeTruthy();
  await act(async () => { root.unmount(); }); root = null;
  routeGet({ "/marketing/posts": [], "/marketing/campaigns": [], "/marketing/meta": {} });
  await mount(<ContentCalendar currentUser={{ permissions: perms }} selectedEntity="ent_ksc" />);
  expect(q("mkt-filter-platform")).toBeNull();
  expect(q("mkt-mode-list").getAttribute("role")).toBe("tab");
  await click(q("mkt-filter-toggle"));
  await change(q("mkt-filter-platform"), "instagram");
  expect(q("mkt-filter-toggle").textContent).toMatch(/Saring \(1\)/);
  await click(q("mkt-mode-list"));
  expect(q("mkt-list")).toBeTruthy();
});

test("L-10: Induk produk baru — FormModal + 4 bagian bernomor, sumbu varian terlipat dengan ringkasan; galat membuka bagiannya", async () => {
  expect(axesSummary([{ label: "Asal", options: [1, 2] }, { label: "Grade", options: [1, 2, 3] }])).toBe("Asal (2) × Grade (3) · 6 kombinasi");
  await mount(<FamilyForm template={null} onClose={() => {}} onSaved={() => {}} />);
  expect(q("family-form-dialog").getAttribute("role")).toBe("dialog");
  expect([...document.querySelectorAll(".form-section-num")].map((n) => n.textContent)).toEqual(["1", "2", "3", "4"]);
  expect(q("family-sec-axes-body").hidden).toBe(true);                       // sumbu varian terlipat bawaan
  expect(q("family-sec-axes-summary").textContent).toMatch(/kombinasi/);
  expect(q("catalog-axis-editor")).toBeTruthy();                             // isian tetap terpasang walau terlipat
  expect(q("family-form-summary").textContent).toMatch(/Induk baru/);
  await setInput(q("family-name"), "Rayon Milano");
  await change(q("family-category"), "KAT");
  await act(async () => { q("family-form").closest("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  expect(q("family-form-dialog-error").textContent).toMatch(/memerlukan minimal satu pilihan/);
  expect(q("family-sec-axes-body").hidden).toBe(false);                      // bagian bermasalah dibuka
});

test("grid HP: di himpunan berkas R4 tidak ada `grid … <bp>:grid-cols-…` tanpa kolom dasar", () => {
  const fs = require("fs");
  const path = require("path");
  const base = path.join(__dirname, "..");
  const files = [];
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).forEach((e) => {
    const p = path.join(d, e.name);
    if (e.isDirectory()) { if (e.name !== "__tests__") walk(p); } else if (/\.jsx?$/.test(e.name)) files.push(p);
  });
  ["rnd", "design", "designer", "hr", "marketing", "catalog"].forEach((d) => walk(path.join(base, d)));
  fs.readdirSync(path.join(base, "sales")).filter((f) => /^(Return.*|SalesReturns|CreateReturnForm|LogisticsCostRow)\.jsx$/.test(f))
    .forEach((f) => files.push(path.join(base, "sales", f)));
  const skip = ["DesignShowcaseModal.jsx", "AiIllustrationPanel.jsx"];   // berkas yatim (tak diimpor)
  const bad = [];
  files.filter((f) => !skip.includes(path.basename(f))).forEach((f) => {
    const src = fs.readFileSync(f, "utf8");
    const re = /className=(?:"([^"]*)"|\{`([^`]*)`\})/g;
    let m;
    while ((m = re.exec(src))) {
      const toks = (m[1] ?? m[2]).split(/\s+/);
      if (!toks.includes("grid")) continue;
      const resp = toks.some((t) => /^(sm|md|lg|xl|2xl):grid-cols-/.test(t));
      const baseCols = toks.some((t) => /^grid-cols-/.test(t));
      if (resp && !baseCols) bad.push(`${path.relative(base, f)}: ${m[0].slice(0, 90)}`);
    }
  });
  expect(bad).toEqual([]);
});

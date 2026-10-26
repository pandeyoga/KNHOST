// Fase 3 · P6 — R&D: D-24b (Labdip/Handfeel/Proofing → satu layar Sample R&D dengan chip jenis + mode Galeri,
// preset alias), D-24c (Ubah spesifikasi = form buat lengkap), D-09 (Desain & Pattern mode Galeri; Galeri
// Desain showcase = pembungkus), L-01 (PageTabs/FilterChips), L-03 (Riwayat Labdip, LifecycleActions).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import RndSamplesView from "../rnd/RndSamplesView";
import SampleTypeGalleryView from "../rnd/SampleTypeGalleryView";
import SpecFormModal, { editPayload, specToForm, targetOf } from "../rnd/SpecFormModal";
import RndDesignsView from "../rnd/RndDesignsView";
import DesignGalleryView from "../hr/DesignGalleryView";
import LabdipHistoryModal from "../rnd/LabdipHistoryModal";
import LifecycleActions from "../rnd/design/LifecycleActions";
import {
  filterSamples, galleryKpis, galleryMatch, purposeParam, statusCounts,
} from "../rnd/sampleViewUtils";
import { activeFilterCount, filterDesigns, rowsForMode, statusOptions, EMPTY_FILTER, EMPTY_DATE } from "../rnd/design/designFilters";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";

const mockListSamples = jest.fn();
const mockListDesigns = jest.fn();
const mockPatchSpec = jest.fn();
const mockLabdip = jest.fn();
const mockLifecycle = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: { get: jest.fn(() => Promise.resolve({ data: [] })), post: jest.fn(() => Promise.resolve({ data: {} })), defaults: { headers: { common: {} } } },
}));
jest.mock("../rnd/rndApi", () => ({
  listSamples: (...a) => mockListSamples(...a),
  sampleTypes: () => Promise.resolve([
    { value: "labdip", label: "Labdip (kain polos)" }, { value: "handfeel", label: "Handfeel" }, { value: "proofing", label: "Proofing" },
  ]),
  picQueue: () => Promise.resolve({ items: [] }),
  roundProofUrl: () => "",
  listDesigns: (...a) => mockListDesigns(...a),
  studioCategories: () => Promise.resolve([]),
  designFileUrl: () => "",
  listColors: () => Promise.resolve([]),
  patchSpec: (...a) => mockPatchSpec(...a),
  createSpec: () => Promise.resolve({}),
  labdipHistory: (...a) => mockLabdip(...a),
  designLifecycle: (...a) => mockLifecycle(...a),
  designNewVersion: () => Promise.resolve({}),
  holdDesign: () => Promise.resolve({}),
  releaseDesignHold: () => Promise.resolve({}),
}));
jest.mock("../../hooks/useDomainEnums", () => ({
  __esModule: true, default: () => ({ options: () => [], labelOf: (k, v) => v || "—", loading: false }),
}));
jest.mock("../../hooks/useCatalogMasters", () => ({
  __esModule: true, default: () => ({ categoryOptions: [], unitOptions: [{ value: "meter", label: "meter" }] }),
}));
jest.mock("../../components/BaseFabricPicker", () => () => null);
jest.mock("../catalog/SpecVariantFields", () => ({ SpecVariantFields: () => <div data-testid="spec-variant-link" /> }));
jest.mock("../rnd/design/DesignImage", () => ({ __esModule: true, default: () => null, IMAGE_FAIL_TEXT: "" }));

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
  [mockListSamples, mockListDesigns, mockPatchSpec, mockLabdip, mockLifecycle].forEach((m) => m.mockReset());
  document.body.innerHTML = "";
});
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); };
const withNav = (role, preset, child, onNavigateTo = () => {}) => (
  <AppNavProvider role={role} onNavigateTo={onNavigateTo} onOpenDocument={() => {}}>
    <ViewPresetProvider preset={preset}>{child}</ViewPresetProvider>
  </AppNavProvider>
);

const S = (id, status, types, rounds = [], extra = {}) => ({
  id, number: `KSC/SMP-${id}`, title: `Sample ${id}`, status, sample_types: types, rounds,
  participants: [{ supplier_id: "sup1", supplier_name: "Mitra A" }], ...extra,
});
const SAMPLES = [
  S("1", "sent", ["labdip"], [{ id: "r1", type_code: "labdip", result: "acc", score: 88, round_no: 1 }]),
  S("2", "in_progress", ["labdip", "handfeel"], [{ id: "r2", type_code: "handfeel", result: "revisi", round_no: 2, overdue: true }]),
  S("3", "cancelled", ["labdip"]),
];

// ── D-24b util ───────────────────────────────────────────────────────────────────────────────────────
test("D-24b util: tujuan server per mode, galeri tanpa batal, KPI per jenis, saringan hasil", () => {
  expect(purposeParam("board", "new_development", "all")).toBe("new_development");
  expect(purposeParam("gallery", "new_development", "all")).toBe("");
  expect(purposeParam("gallery", "", "revalidation")).toBe("revalidation");
  expect(filterSamples(SAMPLES, { gallery: true }).map((s) => s.id)).toEqual(["1", "2"]);
  expect(filterSamples(SAMPLES, { gallery: false }).map((s) => s.id)).toEqual(["1", "2", "3"]);
  expect(filterSamples(SAMPLES, { minRevision: "1" }).map((s) => s.id)).toEqual(["2"]);
  expect(filterSamples(SAMPLES, { q: "mitra a" })).toHaveLength(3);
  expect(statusCounts(SAMPLES, { gallery: true })[""]).toBe(2);
  const k = galleryKpis(SAMPLES, "labdip");
  expect(k).toMatchObject({ total: 2, sent: 1, in_progress: 1, assessed: 1, overdue_rounds: 0 });
  expect(galleryKpis(SAMPLES, "handfeel").overdue_rounds).toBe(1);
  expect(galleryMatch(SAMPLES[0], "labdip", { result: "acc" })).toBe(true);
  expect(galleryMatch(SAMPLES[1], "handfeel", { result: "acc" })).toBe(false);
  expect(galleryMatch(SAMPLES[1], "handfeel", { result: "revisi" })).toBe(true);
  expect(galleryMatch(SAMPLES[0], "labdip", { score: "90" })).toBe(false);
});

// ── D-24b layar ──────────────────────────────────────────────────────────────────────────────────────
test("D-24b: alias rnd-labdip (preset gallery+labdip+all) → Sample R&D mode Galeri, chip Labdip aktif, tanpa saringan tujuan", async () => {
  mockListSamples.mockResolvedValue({ items: SAMPLES, stats: { total: 99 } });
  await mount(withNav("md", { view: "rnd-samples", nonce: 1, mode: "gallery", type: "labdip", purpose: "all" },
    <RndSamplesView currentUser={{ role: "md" }} selectedEntity="ent_ksc" purpose="new_development" />));
  expect(q("rnd-samples-view").getAttribute("data-mode")).toBe("gallery");
  expect(q("rnd-samples-tab-gallery").getAttribute("aria-selected")).toBe("true");
  expect(q("rnd-samples-filter-labdip").getAttribute("aria-pressed")).toBe("true");
  expect(q("rnd-samples-purpose-all").getAttribute("aria-pressed")).toBe("true");
  const params = mockListSamples.mock.calls[mockListSamples.mock.calls.length - 1][0];
  expect(params.sample_type).toBe("labdip");
  expect(params.purpose).toBeUndefined();
  // KPI galeri dari baris (tanpa yang batal), bukan stats server papan
  expect(q("rnd-samples-kpi-total").textContent).toBe("2");
  expect(q("sample-type-card-1")).toBeTruthy();
  expect(q("sample-type-card-3")).toBeNull();
  // Tombol buat = "Buat Permintaan" (jenis dikunci dari chip), bukan "Sample Labdip Baru"
  expect(q("rnd-sample-create-button").textContent).toContain("Buat Permintaan");
});

test("D-24b: Papan bawaan menu Produk Baru — tujuan dari menu, tanpa chip tujuan, status = FilterChips berhitungan", async () => {
  mockListSamples.mockResolvedValue({ items: SAMPLES, stats: { total: 3, sent: 1 } });
  await mount(withNav("md", null, <RndSamplesView currentUser={{ role: "md" }} selectedEntity="ent_ksc" purpose="new_development" />));
  expect(q("rnd-samples-view").getAttribute("data-mode")).toBe("board");
  expect(mockListSamples.mock.calls[0][0].purpose).toBe("new_development");
  expect(q("rnd-samples-purpose")).toBeNull();
  expect(q("rnd-samples-board")).toBeTruthy();
  expect(q("rnd-samples-chip-all").getAttribute("aria-pressed")).toBe("true");
  expect(q("rnd-samples-chip-all").textContent).toContain("3");
  await click(q("rnd-samples-tab-list"));
  expect(q("rnd-sample-row-1")).toBeTruthy();
  expect(q("rnd-samples-kpi-total").textContent).toBe("3");
});

test("D-24b: chip jenis lama mengikuti hak buka id lama (hidden_views / peran tanpa R&D) — tanpa provider tidak digerbang", async () => {
  mockListSamples.mockResolvedValue({ items: [], stats: {} });
  await mount(withNav("designer", null, <RndSamplesView currentUser={{ role: "md" }} selectedEntity="ent_ksc" purpose="new_development" />));
  expect(q("rnd-samples-filter-all")).toBeTruthy();
  expect(q("rnd-samples-filter-labdip")).toBeNull();
  await act(async () => { root.unmount(); }); root = null;
  await mount(<RndSamplesView currentUser={{ role: "md" }} selectedEntity="ent_ksc" purpose="new_development" />);
  expect(q("rnd-samples-filter-labdip")).toBeTruthy();
});

test("D-24b: rute cadangan rnd-handfeel (SampleTypeGalleryView) = pembungkus → layar gabungan mode Galeri, chip Handfeel", async () => {
  mockListSamples.mockResolvedValue({ items: SAMPLES, stats: {} });
  await mount(withNav("md", null, <SampleTypeGalleryView code="handfeel" currentUser={{ role: "md" }} selectedEntity="ent_ksc" />));
  expect(q("sample-gallery-handfeel")).toBeTruthy();
  expect(q("rnd-samples-view").getAttribute("data-mode")).toBe("gallery");
  expect(q("rnd-samples-filter-handfeel").getAttribute("aria-pressed")).toBe("true");
  expect(mockListSamples.mock.calls[0][0]).toMatchObject({ sample_type: "handfeel" });
  expect(mockListSamples.mock.calls[0][0].purpose).toBeUndefined();
});

// ── D-24c ────────────────────────────────────────────────────────────────────────────────────────────
const SPEC = {
  id: "spec_1", number: "KSC/SPEC-00001", status: "draft", title: "Katun 135", category: "Katun", base_unit: "meter",
  sku_hint: "KTN-135", sample_type_hint: "labdip", template_id: "tpl_1", variant_attrs: { color: "Navy" },
  target: { stage: "finished", fabric_type: "woven", gramasi: 135, lebar: null, epi: 60, ppi: null, grade: "A", warp_count: "40s" },
  color_target: { color_id: "clr_1", code: "NVY", name: "Navy" }, design_id: "dsn_1", notes: "awal",
  base_fabric_template_id: "", target_price: 50000,
};

test("D-24c util: isian dari spesifikasi tersimpan; PATCH hanya kirim warna/desain bila berubah & tidak dikunci", () => {
  const f = specToForm(SPEC);
  expect(f).toMatchObject({ title: "Katun 135", gramasi: "135", lebar: "", epi: "60", color_id: "clr_1", design_id: "dsn_1", grade: "A" });
  const body = editPayload(f, SPEC);
  expect(body.color_target).toBeUndefined();
  expect(body.design_id).toBeUndefined();
  expect(body.base_fabric_template_id).toBeUndefined();
  expect(body.target).toMatchObject({ stage: "finished", fabric_type: "woven", gramasi: "135", lebar: null, yarn_count: "" });
  expect(body.target_price).toBeUndefined();   // MD-04: target harga tidak lagi di form; data lama tetap
  const changed = editPayload({ ...f, color_id: "clr_2", design_id: "" }, SPEC);
  expect(changed.color_target).toEqual({ color_id: "clr_2" });
  expect(changed.design_id).toBe("");
  const locked = editPayload({ ...f, color_id: "clr_2", design_id: "" }, SPEC, { colorLocked: true, designLocked: true });
  expect(locked.color_target).toBeUndefined();
  expect(locked.design_id).toBeUndefined();
  expect(targetOf({ ...f, stage: "yarn", yarn_count: "30s" })).toMatchObject({ gramasi: null, epi: null, yarn_count: "30s" });
});

test("D-24c: Ubah spesifikasi = FormModal form lengkap (bukan 6 isian), induk baca-saja, simpan → PATCH", async () => {
  mockPatchSpec.mockResolvedValue({ id: "spec_1" });
  mockListDesigns.mockResolvedValue([]);
  const onSaved = jest.fn();
  await mount(<SpecFormModal spec={SPEC} lockLinks templateName="Katun Premium" types={[]} onClose={() => {}} onSaved={onSaved} />);
  const dlg = q("spec-form-modal");
  expect(dlg.getAttribute("role")).toBe("dialog");
  expect(q("spec-form-modal-title").textContent).toContain("Ubah spesifikasi · KSC/SPEC-00001");
  expect(q("spec-variant-link")).toBeNull();
  expect(q("spec-edit-variant").textContent).toContain("Katun Premium");
  // isian lengkap form buat ikut hadir
  ["spec-title-input", "spec-sample-type", "spec-stage", "spec-fabric", "spec-gramasi-input", "spec-lebar-input", "spec-epi-input",
    "spec-ppi-input", "spec-color", "spec-design", "spec-sku-input", "spec-category-input", "spec-unit-input", "spec-grade", "spec-notes-input"]
    .forEach((id) => expect(q(id)).toBeTruthy());
  expect(q("spec-title-input").value).toBe("Katun 135");
  await click(q("spec-form-save"));
  expect(mockPatchSpec).toHaveBeenCalledTimes(1);
  const [id, body] = mockPatchSpec.mock.calls[0];
  expect(id).toBe("spec_1");
  expect(body).toMatchObject({ title: "Katun 135", sku_hint: "KTN-135", notes: "awal" });
  expect(body.color_target).toBeUndefined();
  expect(onSaved).toHaveBeenCalled();
});

// ── D-09 ─────────────────────────────────────────────────────────────────────────────────────────────
const D = (id, status, extra = {}) => ({ id, code: `DSN-${id}`, title: `Desain ${id}`, status, files: [], ...extra });
const DESIGNS = [
  D("a", "draft"), D("b", "approved", { ownership: "customer", owner_customer_name: "PT X" }),
  D("c", "active", { produced: true }), D("d", "in_review"),
];

test("D-09 util: Galeri = hanya desain ACC; saringan kepemilikan & produksi; status 'acc' preset = semua ACC", () => {
  expect(rowsForMode(DESIGNS, "gallery").map((d) => d.id)).toEqual(["b", "c"]);
  expect(rowsForMode(DESIGNS, "master")).toHaveLength(4);
  expect(filterDesigns(DESIGNS, { ...EMPTY_FILTER, own: "customer" }, EMPTY_DATE).map((d) => d.id)).toEqual(["b"]);
  expect(filterDesigns(DESIGNS, { ...EMPTY_FILTER, produced: "yes" }, EMPTY_DATE).map((d) => d.id)).toEqual(["c"]);
  expect(statusOptions("gallery").map((o) => o.key)).toEqual(["", "approved", "final_submitted", "active"]);
  expect(activeFilterCount({ ...EMPTY_FILTER, status: "approved" }, EMPTY_DATE, "gallery")).toBe(0);
  expect(activeFilterCount({ ...EMPTY_FILTER, status: "approved" }, EMPTY_DATE, "master")).toBe(1);
});

test("D-09: alias cs-design-gallery (preset gallery+acc) → Desain & Pattern mode Galeri; tab Master memuat semua", async () => {
  mockListDesigns.mockResolvedValue(DESIGNS);
  await mount(withNav("admin", { view: "rnd-designs", nonce: 2, mode: "gallery", status: "acc" },
    <RndDesignsView currentUser={{ role: "admin", permissions: {} }} selectedEntity="ent_ksc" />));
  expect(q("rnd-designs-view").getAttribute("data-mode")).toBe("gallery");
  expect(q("gallery-card-b")).toBeTruthy();
  expect(q("gallery-card-c")).toBeTruthy();
  expect(q("gallery-card-a")).toBeNull();
  expect(q("gallery-card-ownership-b").textContent).toContain("Customer label");
  expect(q("rnd-filter-status-all").textContent).toContain("Semua status ACC");
  await click(q("rnd-designs-tab-master"));
  expect(q("design-card-a")).toBeTruthy();
  expect(q("design-card-d")).toBeTruthy();
});

test("D-09: rute cadangan cs-design-gallery (DesignGalleryView) = pembungkus tipis mode Galeri", async () => {
  mockListDesigns.mockResolvedValue(DESIGNS);
  await mount(withNav("admin", null, <DesignGalleryView currentUser={{ role: "admin", permissions: {} }} selectedEntity="ent_ksc" />));
  expect(q("design-gallery-view")).toBeTruthy();
  expect(q("rnd-designs-view").getAttribute("data-mode")).toBe("gallery");
  expect(q("gallery-grid").children).toHaveLength(2);
});

// ── L-03 ─────────────────────────────────────────────────────────────────────────────────────────────
test("L-03: Riwayat Labdip = DetailModal baku (role dialog, tabel bergulir di dalam), Esc menutup", async () => {
  mockLabdip.mockResolvedValue({ items: [], waiting: [], summary: {} });
  const onClose = jest.fn();
  await mount(<LabdipHistoryModal colorId="clr_1" label="NVY · Navy" onClose={onClose} />);
  expect(q("labdip-history-modal").getAttribute("role")).toBe("dialog");
  expect(q("labdip-history-empty")).toBeTruthy();
  expect(document.body.querySelector(".modal-card")).toBeNull();
  await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
  expect(onClose).toHaveBeenCalled();
});

test("L-03: aksi siklus desain = FormModal; alasan wajib tampil sebagai galat di dalam dialog", async () => {
  const design = { id: "dsn_1", code: "DSN-1", status: "pending_approval", version: 1, rounds: [{ version: 1, file_count: 1 }] };
  await mount(<LifecycleActions design={design} canAssess canEdit onDone={() => {}} onError={() => {}} />);
  await click(q("design-action-request_revision"));
  expect(q("design-action-dialog").getAttribute("role")).toBe("dialog");
  expect(document.body.querySelector(".fixed.inset-0.z-\\[190\\]")).toBeNull();
  await click(q("design-action-confirm"));
  expect(q("design-action-dialog-error").textContent).toContain("Catatan wajib diisi");
  expect(mockLifecycle).not.toHaveBeenCalled();
});

// Fase 3 · P8 — aktivasi: gerbang per bagian di layar utama memakai id layar LAMA (§1.1 butir 6 rencana fase 3), supaya
// katalog akses peran kustom & `hidden_views` tetap berlaku setelah layar lama menjadi alias/tab:
//  · D-11 Profitabilitas: tab Realisasi dijaga izin akuntansi; peran kustom modul Laporan → tab katalog saja.
//  · D-29 Perangkat: tab RFID = id `cs-rfid-devices`, tab Mesin absen = id `hr-attendance-setup`.
//  · D-01 Template Dokumen: "Desainer PDF" — kini izin `pdf_template.manage` (02_STANDAR §3 Z2; lihat describe D-01).
//  · D-09 Desain & Pattern: mode Galeri = id `cs-design-gallery`.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import fixture from "../../config/__tests__/fixtures/access_nav_fixture.json";
import { registerDynamicRoles, setAccessContext } from "../../config/roles";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import ProfitabilityView from "../finance/ProfitabilityView";
import DevicesView from "../settings/devices/DevicesView";
import DocTemplatesView from "../pdf/DocTemplatesView";
import RndDesignsView from "../rnd/RndDesignsView";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: {
    get: (...a) => mockGet(...a), post: jest.fn(() => Promise.resolve({ data: {} })),
    patch: jest.fn(() => Promise.resolve({ data: {} })), delete: jest.fn(() => Promise.resolve({ data: {} })),
    defaults: { headers: { common: {} } },
  },
}));
jest.mock("recharts", () => {
  const Box = () => <div />;
  return new Proxy({}, { get: () => Box });
});
jest.mock("../costing/CostingView", () => () => <div data-testid="stub-costing" />);
jest.mock("../hr/AttendanceSetupView", () => () => <div data-testid="stub-absen" />);
jest.mock("../rfid/RfidDevicesView", () => () => <div data-testid="stub-rfid" />);
jest.mock("../settings/masters/EntityMasterKindPanel", () => () => <div data-testid="stub-dasar" />);
jest.mock("../pdf/PdfTemplateDesigner", () => () => <div data-testid="stub-desainer" />);
jest.mock("../admin/DocTemplateForm", () => () => null);
const mockListDesigns = jest.fn();
jest.mock("../rnd/rndApi", () => ({
  listDesigns: (...a) => mockListDesigns(...a),
  studioCategories: () => Promise.resolve([]),
  designFileUrl: () => "",
  listColors: () => Promise.resolve([]),
  designLifecycle: () => Promise.resolve({}),
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
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const withNav = (role, child, preset = null) => (
  <AppNavProvider role={role} onNavigateTo={() => {}} onOpenDocument={() => {}}>
    <ViewPresetProvider preset={preset}>{child}</ViewPresetProvider>
  </AppNavProvider>
);
/** Akun aktif peran kustom: izin efektif + tab yang disembunyikan (setAccessContext seperti App.js). */
const asCustom = (role, permissions, hidden = []) => setAccessContext({ role, permissions, view_resources: {}, hidden_views: hidden });

beforeAll(() => {
  registerDynamicRoles([...fixture,
    { id: "cr_uji_desain", label: "uji", custom: true, base_role: "",
      nav: { add: ["designer-hub", "design-requests", "rnd-designs", "cs-design-gallery"], remove: [] } },
    // Peran kustom tanpa acuan bermodul Dokumen (katalog: `pdf-templates` milik modul `documents`, PR-T5).
    { id: "cr_dokumen", label: "uji dokumen", custom: true, base_role: "",
      nav: { add: ["settings-hub", "settings-documents", "pdf-templates", "document-center", "documents"], remove: [] } }]);
});
afterAll(() => registerDynamicRoles([]));
beforeEach(() => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: String(url).includes("/finance/profitability") ? { totals: {} } : [] }));
});
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  setAccessContext(null);
  mockGet.mockReset(); mockListDesigns.mockReset();
  document.body.innerHTML = "";
});

describe("D-11 — Profitabilitas & Margin", () => {
  test("peran kustom modul Laporan: hanya tab katalog (Realisasi butuh izin akuntansi), tanpa memanggil realisasi", async () => {
    asCustom("cr_reports", { reports: ["view"] });
    await mount(withNav("cr_reports", <ProfitabilityView selectedEntity="ent_ksc" />));
    expect(q("prof-tabs-realisasi")).toBeNull();
    expect(q("prof-tabs-katalog").getAttribute("aria-selected")).toBe("true");
    expect(q("stub-costing")).not.toBeNull();
    expect(mockGet.mock.calls.some(([u]) => String(u).includes("/finance/profitability"))).toBe(false);
  });

  test("admin & peran akuntansi: Realisasi tetap tab pertama; alias costing membuka katalog", async () => {
    setAccessContext({ role: "admin" });   // PR-T7 — Admin yang sudah masuk (canCurrent tanpa konteks = tidak)
    await mount(withNav("admin", <ProfitabilityView selectedEntity="ent_ksc" />,
      { view: "profitability", nonce: 1, tab: "katalog" }));
    expect(q("prof-tabs-realisasi")).not.toBeNull();
    expect(q("prof-tabs-katalog").getAttribute("aria-selected")).toBe("true");
  });
});

describe("D-29 — Perangkat (gerbang per id lama)", () => {
  test("admin: dua tab (Mesin absen + RFID)", async () => {
    await mount(withNav("admin", <DevicesView currentUser={{ role: "admin" }} initialTab="rfid" />));
    expect(q("devices-tabs-absen")).not.toBeNull();
    expect(q("devices-tabs-rfid")).not.toBeNull();
    expect(q("stub-rfid")).not.toBeNull();
  });

  test("manajer: Mesin absen saja (RFID tetap admin, seperti cs-rfid-devices dulu)", async () => {
    await mount(withNav("manager", <DevicesView currentUser={{ role: "manager" }} initialTab="rfid" />));
    expect(q("devices-tabs-rfid")).toBeNull();
    expect(q("stub-absen")).not.toBeNull();
  });

  test("peran kustom Operasi Gudang: tab RFID saja (katalog memuat cs-rfid-devices, bukan Shift & Geofence)", async () => {
    asCustom("cr_warehouse_ops", { wms: ["view"] });
    await mount(withNav("cr_warehouse_ops", <DevicesView currentUser={{ role: "cr_warehouse_ops" }} />));
    expect(q("devices-tabs-absen")).toBeNull();
    expect(q("stub-rfid")).not.toBeNull();
  });

  test("peran kustom SDM: Mesin absen saja; hidden_views cs-rfid-devices dipatuhi", async () => {
    asCustom("cr_hr", { hr: ["view"] });
    await mount(withNav("cr_hr", <DevicesView currentUser={{ role: "cr_hr" }} initialTab="rfid" />));
    expect(q("devices-tabs-rfid")).toBeNull();
    expect(q("stub-absen")).not.toBeNull();
  });
});

// D-01 (Fase 3 · P8, 26 Okt) dulu: "peran kustom modul Admin tetap punya Desainer PDF; manajer tidak" — gerbang
// `roleCanSee(["admin"], role, "pdf-templates")`. Dua hal berubah sesudahnya:
//  · PR-T5 (b8bd0a2, 14 Nov; `docs/blueprint/unit/PR-T5.md` tabel 2) memecah modul Admin; `pdf-templates` pindah ke
//    modul Dokumen (pemilik `pdf_template`). Fixture katalog dibangkitkan ulang: `cr_settings_admin` (Pusat Pengaturan)
//    kini `remove` `pdf-templates` → uji lama merah sejak PR-T5 (tersembunyi karena suite ini gagal dimuat sampai 16 Nov).
//  · 02_STANDAR §3 Z2 — wewenang dari izin: Desainer PDF = alat tulis (`pdf_template.manage`), jadi gerbangnya kini izin
//    itu. Manajer bawaan memegang `pdf_template.manage` (permissions_config; data acuan juga Finance), server menerima
//    simpanannya, dan "Lengkapi PT" mengarahkannya ke sini untuk kop & tanda tangan → kini ia melihat desainernya.
describe("D-01 — Template Dokumen: Desainer PDF mengikuti izin pdf_template.manage", () => {
  const open = async (role, permissions, hidden = []) => {
    asCustom(role, permissions, hidden);
    await mount(withNav(role, <DocTemplatesView currentUser={{ role, permissions }} initialTab="desainer" />));
  };
  test("peran kustom modul Dokumen (Kelola) tanpa peran acuan: tab Desainer PDF ada dan terbuka", async () => {
    await open("cr_dokumen", { document: ["view"], pdf_template: ["view", "manage"] });
    expect(q("doc-templates-tabs-desainer")).not.toBeNull();
    expect(q("stub-desainer")).not.toBeNull();
  });
  test("peran kustom Pusat Pengaturan saja (PR-T5: pdf-templates bukan modulnya): tanpa Desainer PDF", async () => {
    await open("cr_settings_admin", { settings: ["view", "update"] });
    expect(q("doc-templates-tabs-desainer")).toBeNull();
    expect(q("stub-desainer")).toBeNull();
    expect(q("stub-dasar")).not.toBeNull();
  });
  test("modul Dokumen tingkat Lihat saja (pdf_template.view): tanpa desainer — simpan di sana pasti 403", async () => {
    await open("cr_dokumen", { document: ["view"], pdf_template: ["view"] });
    expect(q("doc-templates-tabs-desainer")).toBeNull();
    expect(q("stub-dasar")).not.toBeNull();
  });
  test("Manajer bawaan berizin pdf_template.manage: Desainer PDF ada (izin, bukan nama peran)", async () => {
    setAccessContext({ role: "manager", permissions: { pdf_template: ["view", "manage"] } });
    await mount(withNav("manager", <DocTemplatesView currentUser={{ role: "manager", permissions: { pdf_template: ["view", "manage"] } }} initialTab="desainer" />));
    expect(q("doc-templates-tabs-desainer")).not.toBeNull();
    expect(q("stub-desainer")).not.toBeNull();
  });
  test("Manajer yang izin pdf_template dicabut: tanpa Desainer PDF; hidden_views pdf-templates dipatuhi", async () => {
    setAccessContext({ role: "manager", permissions: { order: ["view"] } });
    await mount(withNav("manager", <DocTemplatesView currentUser={{ role: "manager", permissions: { order: ["view"] } }} initialTab="desainer" />));
    expect(q("doc-templates-tabs-desainer")).toBeNull();
    expect(q("stub-dasar")).not.toBeNull();
    await act(async () => { root.unmount(); });
    host.remove(); root = null;
    await open("cr_dokumen", { pdf_template: ["view", "manage"] }, ["pdf-templates"]);
    expect(q("doc-templates-tabs-desainer")).toBeNull();
    expect(q("stub-desainer")).toBeNull();
  });
});

describe("D-09 — Desain & Pattern: mode Galeri", () => {
  const DESIGNS = [
    { id: "a", code: "D-A", name: "Desain A", status: "draft" },
    { id: "b", code: "D-B", name: "Desain B", status: "approved" },
  ];
  test("hidden_views cs-design-gallery menyembunyikan mode Galeri (preset alias jatuh ke Master)", async () => {
    mockListDesigns.mockResolvedValue(DESIGNS);
    asCustom("cr_uji_desain", { design_request: ["view"] }, ["cs-design-gallery"]);
    await mount(withNav("cr_uji_desain", <RndDesignsView currentUser={{ role: "cr_uji_desain", permissions: {} }} selectedEntity="ent_ksc" />,
      { view: "rnd-designs", nonce: 3, mode: "gallery", status: "acc" }));
    expect(q("rnd-designs-tab-gallery")).toBeNull();
    expect(q("rnd-designs-view").getAttribute("data-mode")).toBe("master");
  });

  test("tanpa hidden_views: mode Galeri tampil untuk peran kustom bermodul Desain", async () => {
    mockListDesigns.mockResolvedValue(DESIGNS);
    asCustom("cr_uji_desain", { design_request: ["view"] });
    await mount(withNav("cr_uji_desain", <RndDesignsView currentUser={{ role: "cr_uji_desain", permissions: {} }} selectedEntity="ent_ksc" />,
      { view: "rnd-designs", nonce: 4, mode: "gallery", status: "acc" }));
    expect(q("rnd-designs-tab-gallery")).not.toBeNull();
    expect(q("rnd-designs-view").getAttribute("data-mode")).toBe("gallery");
  });
});

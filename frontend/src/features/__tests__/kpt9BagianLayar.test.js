// KP-T9 — layar wadah lama dibuka satu bagian (`only`) sebagai tab hub sendiri, kartu tautan pengaturan di luar grup
// (U12, KP-29), pemilih PT "Semua PT", tujuan "Lengkapi" kesiapan PT. Isi tiap bagian tidak diuji di sini (komponen
// anak diganti penanda); yang diuji: bagian mana yang tampil dan apakah bilah tab dalam dirender.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/DesktopOnlyNotice", () => () => null);
jest.mock("../settings/entities/entityApi", () => ({
  listEntities: jest.fn(() => Promise.resolve([])),
  errText: (e, d) => d,
}));
jest.mock("../settings/entities/EntityList", () => () => <div data-testid="isi-entities" />);
jest.mock("../settings/entities/AccountList", () => () => <div data-testid="isi-accounts" />);
jest.mock("../settings/entities/RoleAccessPanel", () => (p) => (
  <div data-testid="isi-roles">{p.onOpenAccounts ? <button type="button" data-testid="isi-roles-buka-akun" onClick={p.onOpenAccounts} /> : null}</div>
));
jest.mock("../settings/entities/RoleRealityPanel", () => () => <div data-testid="isi-role-reality" />);
jest.mock("../settings/entities/EntityReadinessPanel", () => () => <div data-testid="isi-readiness" />);
jest.mock("../settings/entities/EntityWizard", () => () => null);
jest.mock("../settings/entities/EntityDetailDrawer", () => (p) => <div data-testid="isi-detail-pt">{p.entityId}</div>);
jest.mock("../hr/AttendanceSetupView", () => (p) => <div data-testid={`isi-absen-${p.only}`} />);
jest.mock("../rfid/RfidDevicesView", () => () => <div data-testid="isi-rfid" />);
jest.mock("../admin/scheduler/SchedulerWa", () => ({
  WaSettingsPanel: () => <div data-testid="isi-wa" />, WaOutboxTable: () => <div data-testid="isi-wa-outbox" />,
}));
jest.mock("../admin/scheduler/SchedulerPolicy", () => ({
  EscalationPanel: () => <div data-testid="isi-eskalasi" />, DigestPreview: () => null,
}));
jest.mock("../settings/config/SettingsHub", () => ({
  COMMISSION_LINK: null, SettingsNotice: () => null, SettingsBrowser: () => <div data-testid="isi-kartu-pengaturan" />,
  useSettingsBrowser: () => ({ groups: [] }),
}));
jest.mock("../designer/DivisionsView", () => () => null);

/* eslint-disable import/first */
import EntitiesAccessView from "../settings/entities/EntitiesAccessView";
import DevicesView from "../settings/devices/DevicesView";
import SchedulerView from "../admin/scheduler/SchedulerView";
import SettingsGroupView from "../settings/cfg/SettingsGroupView";
import SettingsLinkCards from "../settings/cfg/SettingsLinkCards";
import { SETTINGS_LINKS } from "../settings/config/configGroupViews";
import EntitySwitcher from "../../components/EntitySwitcher";
import { completionPreset, completionView } from "../settings/entities/EntityCompletionSteps";
import RoleNavTree, { inheritedHiddenBy } from "../settings/entities/RoleNavTree";
import AppNavContext from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import { breadcrumbFor, resolveDeepLinkTarget } from "../../config/navigationConfig";
import { registerDynamicRoles, setAccessContext } from "../../config/roles";
import builtin from "../../config/__tests__/fixtures/access_builtin_fixture.json";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const qa = (pre) => [...document.body.querySelectorAll(`[data-testid^="${pre}"]`)].map((n) => n.getAttribute("data-testid"));
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
const navFor = (role) => ({
  role, go: jest.fn(), openDocument: () => {}, canOpen: (v) => !!resolveDeepLinkTarget(v, role),
});
async function mount(el, { role = "admin", preset = null } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  const nav = navFor(role);
  await act(async () => {
    root.render(
      <AppNavContext.Provider value={nav}>
        <ViewPresetProvider preset={preset}>{el}</ViewPresetProvider>
      </AppNavContext.Provider>,
    );
  });
  await flush();
  return { host, nav };
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  mockGet.mockReset();
  setAccessContext(null);
  registerDynamicRoles([]);
});
const ADMIN = { role: "admin", permissions: { entity: ["view", "create", "update"], user: ["view"], permission: ["view", "update"],
  scheduler: ["view", "run", "configure"], hr: ["view", "manage_attendance"] } };

// ── EntitiesAccessView `only` ────────────────────────────────────────────────────────────────────────────────────
describe("Badan Usaha & Akses dipecah: satu bagian per tab hub, tanpa bilah tab dalam", () => {
  test.each([["entities", "isi-entities"], ["readiness", "isi-readiness"], ["accounts", "isi-accounts"],
    ["roles", "isi-roles"], ["role-reality", "isi-role-reality"]])("only=%s → hanya %s", async (only, isi) => {
    await mount(<EntitiesAccessView currentUser={ADMIN} only={only} />);
    expect(q("entities-access-tabs")).toBeNull();
    expect(qa("isi-").filter((t) => !t.startsWith("isi-roles-"))).toEqual([isi]);
    expect(!!q("entity-add-button")).toBe(only === "entities");   // Tambah PT hanya di Profil PT
    // Pola UI 16 Nov (M43): Peran & Hak Akses memuat ulang dari bilah daftarnya sendiri (`role-access-refresh` di
    // RoleAccessPanel, diuji di polaUiPengaturan) — bilah atas tidak menyisakan tombol muat ulang sendirian di satu baris.
    expect(!!q("entities-access-refresh")).toBe(only !== "roles");
    expect(!!q("entities-access-intro")).toBe(only !== "roles");   // pita penjelas → ikon ?
  });

  test("tanpa `only` (rute lama tidak dipakai lagi) bilah tab dalam tetap ada", async () => {
    await mount(<EntitiesAccessView currentUser={ADMIN} />);
    expect(q("entities-access-tabs")).not.toBeNull();
  });

  test("Peran & Hak Akses → tombol buka akun berpindah ke tab Akun (jalur navigasi baku)", async () => {
    const { nav } = await mount(<EntitiesAccessView currentUser={ADMIN} only="roles" />);
    await act(async () => { q("isi-roles-buka-akun").click(); });
    expect(nav.go).toHaveBeenCalledWith("settings-accounts");
  });

  test("Profil PT membaca preset id PT (Lengkapi) dan membuka detail PT aktif", async () => {
    await mount(<EntitiesAccessView currentUser={ADMIN} selectedEntity="ent_ksc" only="entities" />,
      { preset: { view: "settings-pt-profile", entity_id: "ent_ksc", nonce: 1 } });
    expect(q("isi-detail-pt").textContent).toBe("ent_ksc");
  });

  test("bagian tanpa izin: kalimat akses, bukan isi bagian lain", async () => {
    await mount(<EntitiesAccessView currentUser={{ role: "cr_x", permissions: { entity: ["view"] } }} only="accounts" />);
    expect(q("isi-accounts")).toBeNull();
    expect(q("isi-entities")).toBeNull();
    expect(q("entities-access-no-part").textContent).toContain("Akun Pengguna");
  });
});

// ── DevicesView / SchedulerView `only` ───────────────────────────────────────────────────────────────────────────
describe("Perangkat & Penjadwal dipecah", () => {
  test("Mesin Absen (only=absen) dan Perangkat RFID (only=rfid) tanpa bilah tab dalam", async () => {
    await mount(<DevicesView currentUser={ADMIN} only="absen" />);
    expect(q("devices-tabs")).toBeNull();
    expect(qa("isi-")).toEqual(["isi-absen-device"]);
    roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = "";
    await mount(<DevicesView currentUser={ADMIN} only="rfid" />);
    expect(q("devices-tabs")).toBeNull();
    expect(qa("isi-")).toEqual(["isi-rfid"]);
  });

  const SCHED = { "/scheduler/jobs": { jobs: [], running: true }, "/scheduler/summary": { wa: { total: 2 } },
    "/scheduler/runs": [], "/scheduler/settings": { wa: {}, escalation: {} }, "/scheduler/wa-outbox": { items: [], stats: {} } };
  const route = () => mockGet.mockImplementation((url) => Promise.resolve({ data: SCHED[url.replace("/api", "")] || {} }));

  test("Pengingat Otomatis (only=jobs,runs): dua tab dalam, tanpa WhatsApp", async () => {
    route();
    await mount(<SchedulerView currentUser={ADMIN} only={["jobs", "runs"]} />);
    expect(qa("sched-tab-")).toEqual(["sched-tab-jobs", "sched-tab-runs"]);
    expect(q("sched-kpi-wa")).toBeNull();
    expect(q("sched-run-all")).not.toBeNull();
    expect(q("isi-wa")).toBeNull();
  });

  test("WhatsApp (only=wa): tanpa bilah tab dalam, tanpa KPI & tombol job", async () => {
    route();
    await mount(<SchedulerView currentUser={ADMIN} only={["wa"]} />);
    expect(qa("sched-tab-")).toEqual([]);
    expect(q("isi-wa")).not.toBeNull();
    expect(q("isi-wa-outbox")).not.toBeNull();
    expect(q("sched-kpi-jobs")).toBeNull();
    expect(q("sched-run-all")).toBeNull();
    expect(q("sched-kpi-wa")).not.toBeNull();
  });
});

// ── U12 — kartu tautan pengaturan di luar grup (KP-29) ───────────────────────────────────────────────────────────
describe("U12 — kartu tautan di bawah daftar kartu pengaturan", () => {
  test("letak tiap tautan = nama menu tujuannya (breadcrumb menu)", () => {
    const all = Object.values(SETTINGS_LINKS).flat();
    expect(all.map((l) => l.view)).toEqual(["interco-transactions", "bank-accounts", "entity-masters", "md-warehouses",
      "document-center"]);
    all.forEach((l) => expect([l.view, l.where]).toEqual([l.view, breadcrumbFor(l.view, null, "admin").join(" › ")]));
  });

  test("Aturan Keuangan & Pajak sebagai admin: tiga kartu tautan", async () => {
    await mount(<SettingsGroupView view="settings-cfg-finance" currentUser={ADMIN} entities={[]} />);
    expect(qa("cfg-link-").filter((t) => !t.endsWith("-open"))).toEqual(
      ["cfg-link-interco-transactions", "cfg-link-bank-accounts", "cfg-link-entity-masters"]);
    expect(q("cfg-link-bank-accounts").textContent).toContain("Rekening bank dan kas tiap PT");
    expect(q("cfg-link-bank-accounts").textContent).toContain("Keuangan › Kas & Bank › Rekening & Saldo");
  });

  test("peran tanpa izin kas: kartu Rekening bank dan kas tidak tampil", async () => {
    const add = ["settings-hub", "settings-finance", "settings-cfg-finance", "keuangan", "interco-transactions",
      "settings-company", "entity-masters"];
    registerDynamicRoles([{ id: "cr_tanpa_kas", label: "Tanpa Kas", custom: true, base_role: "", nav: { add, remove: [] } }]);
    setAccessContext({ role: "cr_tanpa_kas", permissions: { settings: ["view"], interco: ["view"], entity: ["view"] },
      view_resources: builtin.view_resources, hidden_views: [], view_actions: builtin.view_actions });
    await mount(<SettingsGroupView view="settings-cfg-finance" currentUser={{ role: "cr_tanpa_kas", permissions: {} }} entities={[]} />,
      { role: "cr_tanpa_kas" });
    expect(qa("cfg-link-").filter((t) => !t.endsWith("-open"))).toEqual(
      ["cfg-link-interco-transactions", "cfg-link-entity-masters"]);
  });

  test("Aturan Gudang & Mutu: tautan Daftar gudang; WhatsApp: tautan Pusat Dokumen", async () => {
    await mount(<SettingsGroupView view="settings-cfg-warehouse" currentUser={ADMIN} entities={[]} />);
    expect(qa("cfg-link-").filter((t) => !t.endsWith("-open"))).toEqual(["cfg-link-md-warehouses"]);
    roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = "";
    await mount(<SettingsLinkCards view="settings-whatsapp" />);
    expect(q("cfg-link-document-center").textContent).toContain("WhatsApp untuk mengirim dokumen dan aturan kirim otomatis");
    expect(q("settings-all-link")).toBeNull();
  });
});

// ── Pemilih PT ──────────────────────────────────────────────────────────────────────────────────────────────────
test("pemilih PT: 'Semua PT' (bukan 'Semua Entitas'); teks cadangan 'PT'", async () => {
  await mount(<EntitySwitcher entities={[{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }]} value="all" />);
  expect(q("entity-switcher").textContent).toContain("Semua PT");
  await act(async () => { q("entity-switcher").click(); });
  expect(q("entity-option-all").textContent).toContain("Semua PT");
  expect(document.body.textContent).not.toMatch(/Entitas|badan usaha/i);
  roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = "";
  await mount(<EntitySwitcher entities={[]} value="" canSwitch={false} />);
  expect(q("entity-switcher-locked").textContent).toContain("PT");
  expect(q("entity-switcher-locked").textContent).not.toMatch(/badan usaha/i);
});

// ── "Lengkapi" kesiapan PT ──────────────────────────────────────────────────────────────────────────────────────
test("Lengkapi: tujuan tab hub baru; id lama `entities-access` + tab dari data lama tetap dipetakan", () => {
  expect(completionView({ view: "settings-pt-profile", tab: "entities" })).toBe("settings-pt-profile");
  expect(completionPreset({ view: "settings-pt-profile", tab: "entities" }, "ent_b")).toEqual({ entity_id: "ent_b" });
  expect(completionView({ view: "settings-accounts", tab: "accounts" })).toBe("settings-accounts");
  expect(completionPreset({ view: "settings-accounts", tab: "accounts" }, "ent_b")).toBeNull();
  expect(completionView({ view: "entities-access", tab: "accounts" })).toBe("settings-accounts");
  expect(completionView({ view: "entities-access" })).toBe("settings-pt-profile");
  expect(completionPreset({ view: "entities-access", tab: "entities" }, "ent_b")).toEqual({ entity_id: "ent_b" });
  expect(completionView({ view: "md-warehouses" })).toBe("md-warehouses");
  expect(completionPreset({ view: "receiving", tab: "mode" }, "ent_b")).toEqual({ tab: "mode" });
});

// ── Editor peran: tab pecahan yang ikut tersembunyi bersama wadah lamanya ditulis apa adanya ────────────────────────
test("editor peran: tab ber-inheritsHiddenFrom yang ikut tersembunyi → centang mati + alasan di samping", async () => {
  expect(inheritedHiddenBy("permission-matrix", new Set(["entities-access"]))).toBe("entities-access");
  expect(inheritedHiddenBy("settings-whatsapp", new Set(["scheduler"]))).toBe("scheduler");
  expect(inheritedHiddenBy("entity-masters", new Set(["entities-access"]))).toBe("");
  const mod = { id: "roles", nav: ["settings-hub", "settings-access", "permission-matrix", "settings-role-check", "entities-access"] };
  await mount(<RoleNavTree module={mod} hidden={new Set(["entities-access"])} original={new Set(["entities-access"])}
    onToggle={() => {}} onSetMany={() => {}} />);
  const cek = q("role-nav-tab-roles-permission-matrix");
  expect(cek.disabled).toBe(true);
  expect(cek.checked).toBe(false);
  expect(q("role-nav-tab-inherited-roles-permission-matrix").textContent)
    .toBe("(ikut disembunyikan bersama Badan Usaha & Akses)");
  expect(q("role-nav-menu-roles-settings-access").textContent).toContain("0/2 tab");
});

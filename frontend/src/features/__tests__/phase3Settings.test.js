// Fase 3 · P2 — Pengaturan & master data: susunan menu P16-K1 (grup Pengaturan, 7 kelompok), kelompok registri →
// layar domain (tanpa kelompok yatim), deep link openConfig per peran, kunci komisi tidak tampil ganda (D-03),
// Aturan Persetujuan mode baca manajer (D-04), alias D-01/D-21/D-29, peringatan kategori kembar (D-02), tabel
// Satuan & faktor (D-21).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import fs from "fs";
import path from "path";
import { HUB_TABS, NAV_STRUCTURE, buildNavGroups, hubTabsForRole, resolveDeepLinkTarget } from "../../config/navigationConfig";
import { resolveAlias } from "../../config/viewAliases";
import { CONFIG_GROUP_VIEWS, CONFIG_GROUP_VIEW_IDS, configTargetFor, configViewForGroup } from "../settings/config/configGroupViews";
import { CONFIG_GROUPS } from "../settings/config/configDeepLink";
import { configDeepLinkTarget } from "../../hooks/useDeepLinks";
import { sharedAccountGroups } from "../pettycash/ExpenseCategoriesView";
import { buildUnitRows } from "../admin/uom/UomUnitsPanel";
import { configApi } from "../settings/config/configApi";
import SettingsHub from "../settings/config/SettingsHub";
import SettingsGroupView from "../settings/cfg/SettingsGroupView";
import ApprovalRulesSettings from "../settings/ApprovalRulesSettings";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../designer/DivisionsView", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
afterEach(() => { mockGet.mockReset(); document.body.innerHTML = ""; jest.restoreAllMocks(); });

const settingsGroup = () => NAV_STRUCTURE.find((e) => e.groupId === "settings-hub");
const menu = (role) => {
  const g = buildNavGroups(role, { showComingSoon: false }).find((x) => x.groupId === "settings-hub");
  return g ? Object.fromEntries(g.items.map((it) => [it.id, hubTabsForRole(it.hub, role).map((t) => t.view)])) : null;
};

// KP-T9 — susunan P16-K1 (12 hub + 2 sub-judul) diganti sembilan hub tanpa sub-judul; uji susunan lengkap di
// config/__tests__/kpt9HubPengaturan.test.js (U3). Yang tetap diuji di sini: grup, tanpa hub `settings-hub`, alias P2.
describe("P16-K1 → KP-T9 — menu Pengaturan sembilan hub", () => {
  test("Pengaturan = grup (groupId tetap settings-hub), sembilan hub tanpa sub-judul", () => {
    const g = settingsGroup();
    expect(g.type).toBe("group");
    const ids = g.items.map((i) => i.id);
    expect(ids).toEqual(["settings-company", "settings-access", "settings-approval", "settings-sales",
      "settings-warehouse", "settings-finance", "settings-hr", "settings-documents", "settings-system"]);
    expect(g.items.filter((i) => i.type === "heading")).toEqual([]);
    expect(HUB_TABS["settings-hub"]).toBeUndefined();
    // "Cari Semua Pengaturan" tetap di menu (audit_config_wiring) — di Sistem.
    expect(HUB_TABS["settings-system"].map((t) => t.view)).toEqual(expect.arrayContaining(["settings-config", "settings-devices", "admin"]));
  });

  test("tiap view hanya di satu hub; Kebijakan Retur pindah dari hub Retur; Koreksi Harga di Produk & Harga", () => {
    const seen = {};
    Object.entries(HUB_TABS).forEach(([hub, tabs]) => tabs.forEach((t) => { (seen[t.view] = seen[t.view] || []).push(hub); }));
    expect(Object.entries(seen).filter(([, hubs]) => hubs.length > 1)).toEqual([]);
    expect(HUB_TABS["returns-hub"].map((t) => t.view)).not.toContain("return-policies");
    expect(seen["return-policies"]).toEqual(["settings-sales"]);
    expect(seen["price-corrections"]).toEqual(["products-pricing"]);
  });

  test("peran: admin semua kelompok; manajer membaca aturan persetujuan; Admin Gudang & Admin Sales tab yang sama seperti dulu", () => {
    expect(Object.keys(menu("admin"))).toHaveLength(9);
    expect(menu("manager")["settings-approval"]).toContain("approval-rules");
    // KP-T9 — Perangkat RFID khusus admin (seperti bagian RFID dulu); mesin absen manajer di SDM › Mesin Absen.
    expect(menu("manager")["settings-system"]).toEqual(["domain-registry", "settings-cfg-system", "settings-config"]);
    expect(menu("manager")["settings-hr"]).toContain("settings-attendance-devices");
    expect(menu("warehouse_admin")).toEqual({ "settings-warehouse": ["settings-receiving-ocr", "grade-master"] });
    expect(menu("sales_admin")).toEqual({ "settings-sales": ["return-policies"], "settings-warehouse": ["grade-master"] });
    // MN-T1 (IA-06) — tab Pemetaan Akun mencantumkan Finance (izin gl_mapping view/update), kini terjangkau lewat ROLE_NAV.
    expect(menu("finance")).toEqual({ "settings-finance": ["gl-account-mappings"] });
    ["sales", "md", "designer", "driver"].forEach((r) => expect(menu(r)).toBeNull());
  });

  test("alias P2: settings-hub (legacy), doc-templates-basic → tab dasar, cs-rfid-devices → tab RFID, uom-conversions", () => {
    expect(resolveAlias("settings-hub")).toMatchObject({ to: "grade-master", legacy: true });
    expect(resolveDeepLinkTarget("settings-hub", "warehouse_admin")).toMatchObject({ view: "grade-master" });
    expect(resolveDeepLinkTarget("doc-templates-basic", "admin")).toMatchObject({
      view: "pdf-templates", navId: "settings-documents", preset: { tab: "dasar" } });
    expect(resolveDeepLinkTarget("cs-rfid-devices", "admin")).toMatchObject({
      view: "settings-devices", navId: "settings-system", preset: { tab: "rfid" } });
    expect(resolveDeepLinkTarget("uom-conversions", "md")).toMatchObject({ view: "md-uoms" });
    expect(resolveDeepLinkTarget("settings-devices", "sales")).toBeNull();
  });
});

describe("kelompok registri → layar domain (tanpa yatim)", () => {
  test("14 kelompok registri masing-masing tepat di SATU layar settings-cfg-*", () => {
    // KF-T4 — 13 kelompok bersub-judul; daftar dibaca dari configKeyIndex.json (dibangkitkan dari registry; uji
    // backend test_KFT4_registry.py menegaskan berkas = keluaran skrip). KF-T7 — + "Keamanan akun & sesi"
    // (`keamanan`) di layar Integrasi & Sistem bersama `sistem`.
    const ids = CONFIG_GROUPS.map((g) => g.id);
    expect(ids).toHaveLength(14);
    expect(configViewForGroup("keamanan")).toBe("settings-cfg-system");
    const owners = ids.map((g) => [g, CONFIG_GROUP_VIEW_IDS.filter((v) => CONFIG_GROUP_VIEWS[v].groups.includes(g))]);
    expect(owners.filter(([, v]) => v.length !== 1)).toEqual([]);
    expect(configViewForGroup("penerimaan")).toBe("settings-cfg-warehouse");
  });

  test("setiap settings-cfg-* ada di menu, berjudul, dan dirender router", () => {
    const tabViews = new Set(Object.values(HUB_TABS).flat().map((t) => t.view));
    const router = fs.readFileSync(path.join(__dirname, "../../AppViewRouter.jsx"), "utf8");
    const { PAGE_META } = require("../../config/navMeta");
    CONFIG_GROUP_VIEW_IDS.forEach((v) => {
      expect([v, tabViews.has(v)]).toEqual([v, true]);
      expect([v, !!PAGE_META[v]]).toEqual([v, true]);
      expect([v, router.includes(`"${v}"`)]).toEqual([v, true]);
    });
  });

  test("deep link openConfig: komisi → Komisi & Insentif; kelompok → layar domain; MD (K-11) tetap Semua pengaturan", () => {
    // MN-T1 — Komisi & Insentif kini SDM › Kinerja & Insentif › Target & Aturan (menu `hr-kpi-hub`).
    expect(configTargetFor({ key: "commission.strategy" })).toEqual({ view: "incentive-rates", nav: "hr-kpi-hub" });
    // KP-T9 — Aturan Pembelian & Makloon dan R&D & Desain kini tab Gudang, Pembelian & Produksi.
    expect(configTargetFor({ group: "makloon", key: "makloon.contract_mode" })).toEqual({ view: "settings-cfg-purchasing", nav: "settings-warehouse" });
    expect(configTargetFor({ key: "tidak_dikenal.x" })).toEqual({ view: "settings-config", nav: "settings-system" });
    expect(configDeepLinkTarget({ group: "rnd" }, "admin")).toEqual({ view: "settings-cfg-rnd", nav: "settings-warehouse" });
    expect(configDeepLinkTarget({ group: "rnd" }, "md")).toEqual({ view: "settings-config", nav: "settings-system" });
    expect(configDeepLinkTarget({ key: "ai.sales_definition", group: "asisten-analitik" }, "manager"))
      .toEqual({ view: "settings-cfg-system", nav: "settings-system" });
    // KF-T4 — id kelompok lama diterjemahkan (GROUP_ALIASES); kunci → kelompoknya dari indeks registry.
    expect(configTargetFor({ group: "dokumen" })).toEqual({ view: "settings-cfg-approval", nav: "settings-approval" });
    expect(configTargetFor({ key: "receiving.ocr_enabled" })).toEqual({ view: "settings-cfg-system", nav: "settings-system" });
    expect(configTargetFor({ key: "payment.variance_ap_tolerance_rupiah" }))
      .toEqual({ view: "settings-cfg-purchasing", nav: "settings-warehouse" });
  });
});

describe("D-03 — kunci commission.* tidak tampil ganda", () => {
  const item = (key, group, label) => ({
    key, group, label, value: 1, default: 1, type: "int", status: "active", scopes: ["global"], help: "", impact: "",
    example: "", source_layer: "code_default", source_label: "Bawaan sistem", can_edit: true,
  });
  // KF-T4 — kelompok baru (penjualan, retur-koreksi, pajak-pembukuan) bersub-judul.
  const items = [item("commission.strategy", "penjualan", "Strategi komisi"), item("pricing.max_discount", "penjualan", "Diskon maks"),
    item("returns.photo_required", "retur-koreksi", "Foto retur"), item("tax.ppn_rate", "pajak-pembukuan", "PPN")];
  const groups = [
    { id: "penjualan", label: "Penjualan & harga", question: "?", count: 2, sections: [{ id: "harga", label: "Harga & diskon" }] },
    { id: "retur-koreksi", label: "Retur & koreksi dokumen", question: "?", count: 1, sections: [{ id: "retur", label: "Retur" }] },
    { id: "pajak-pembukuan", label: "Pajak, pembukuan & antar-PT", question: "?", count: 1, sections: [{ id: "pajak", label: "Pajak" }] },
  ];
  function spy() {
    jest.spyOn(configApi, "registry").mockResolvedValue({ groups, entries: items, caps: { settings_manage: true, global_write: true } });
    jest.spyOn(configApi, "health").mockResolvedValue({ rows: [] });
    return jest.spyOn(configApi, "effective").mockImplementation(async ({ group, q: term }) => ({
      items: items.filter((i) => (term ? i.key.includes(term) : i.group === group)) }));
  }

  test("Semua pengaturan: kunci komisi disembunyikan + tautan ke Komisi & Insentif; tab Koreksi Harga dicabut", async () => {
    spy();
    const { host } = await mount(<SettingsHub currentUser={{ role: "admin" }} entities={[]} />);
    expect(q(host, "cfg-card-wrap-pricing.max_discount")).not.toBeNull();
    expect(q(host, "cfg-card-wrap-commission.strategy")).toBeNull();
    expect(q(host, "cfg-commission-link-readonly") || q(host, "cfg-commission-link")).not.toBeNull();
    expect(q(host, "cfg-tab-impact")).toBeNull();
    expect(q(host, "cfg-tab-settings")).not.toBeNull();
  });

  test("Aturan Penjualan (settings-cfg-sales): hanya kelompok domainnya, tanpa kunci komisi", async () => {
    const eff = spy();
    const { host } = await mount(<SettingsGroupView view="settings-cfg-sales" currentUser={{ role: "admin" }} entities={[]} />);
    expect(q(host, "cfg-group-penjualan")).not.toBeNull();
    expect(q(host, "cfg-group-retur-koreksi")).not.toBeNull();
    expect(q(host, "cfg-group-pajak-pembukuan")).toBeNull();
    expect(q(host, "cfg-card-wrap-commission.strategy")).toBeNull();
    expect(q(host, "cfg-card-wrap-pricing.max_discount")).not.toBeNull();
    expect(eff.mock.calls.every(([p]) => p.group !== "pajak-pembukuan")).toBe(true);
  });
});

describe("D-04 — Aturan Persetujuan: manajer membaca (KP-T4: satu tabel kebijakan)", () => {
  // KP-T4 — isi layar KP-T3/D-04 (tabel `approval_rules` + tombol Nonaktifkan) digantikan Aturan Persetujuan satu tabel;
  // jalur tulis lama dimatikan server. Yang tetap: manajer membaca tanpa tombol ubah, admin punya tombol ubah.
  const TRF = { doc_kind: "transfer", label: "Transfer gudang", group: "Gudang", has_amount: false, source: "grup",
    version: 1, permission_label: "Stok & Persediaan", warnings: [], unused_group_rows: [], note: "",
    levels: [{ level: 1, label: "Persetujuan", tiers: [{ id: "t1", min_amount: 0, max_amount: null, roles: [],
      role_labels: [], any_holder: true, passing_labels: ["Semua pemegang akses"], no_permission_labels: [] }] }] };
  const route = () => mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/approval-policies")
    ? { entity_id: "all", kinds: [TRF] } : url.endsWith("/approval-policies/kinds") ? { kinds: [], roles: [] } : [] }));
  test("tanpa settings.manage: aturan tampil baca-saja (tanpa Ubah)", async () => {
    route();
    const { host } = await mount(<ApprovalRulesSettings currentUser={{ role: "manager", permissions: { settings: ["view"] } }} />);
    expect(q(host, "appol-card-transfer")).not.toBeNull();
    expect(q(host, "approval-rules-readonly")).not.toBeNull();
    expect(q(host, "appol-edit-transfer")).toBeNull();
  });

  test("dengan settings.manage: tombol Ubah membuka pop-up baku tanpa centang Aktif", async () => {
    route();
    const { host } = await mount(<ApprovalRulesSettings currentUser={{ role: "admin", permissions: { settings: ["view", "manage"] } }} />);
    await act(async () => { q(host, "appol-edit-transfer").click(); });
    expect(document.body.querySelector('[data-testid="appol-editor"]')).not.toBeNull();
    expect(q(host, "rule-active")).toBeNull();
  });
});

test("D-02 — kategori aktif di lapisan sama dengan akun sama = peringatan kembar (data tidak diubah)", () => {
  const rows = [
    { code: "office_supplies", label: "Office Supplies", account_code: "6-4100", entity_scope: "global", active: true },
    { code: "atk", label: "ATK", account_code: "6-4100", entity_scope: "global", active: true },
    { code: "atk", label: "ATK KSC", account_code: "6-4100", entity_scope: "entity", entity_id: "ent_ksc", active: true },
    { code: "lunch", label: "Lunch", account_code: "6-4200", entity_scope: "global", active: true },
    { code: "old", label: "Lama", account_code: "6-4200", entity_scope: "global", active: false },
  ];
  expect(sharedAccountGroups(rows)).toEqual([{ account: "6-4100", labels: ["Office Supplies", "ATK"] }]);
});

test("D-21 — Satuan & faktor: faktor dari master / aturan tetap / satuan dasar, aturan terpakai tidak diulang", () => {
  const units = [
    { code: "meter", label: "Meter (m)", dimension: "length" }, { code: "yard", label: "Yard (yd)", dimension: "length" },
    { code: "cm", label: "Centimeter (cm)", dimension: "length" }, { code: "roll", label: "Roll", dimension: "count" },
  ];
  const master = [
    { code: "MTR", name: "Meter", base_type: "length", factor_to_base: 1, aliases: ["meter", "m"], status: "active" },
    { code: "YRD", name: "Yard", base_type: "length", factor_to_base: 0.9144, aliases: ["yard"], status: "active" },
  ];
  const rules = [{ id: "r-cm", kind: "fixed", status: "active", from_unit: "cm", to_unit: "meter", factor: 0.01 },
    { id: "r-roll", kind: "pack", status: "active", from_unit: "roll", to_unit: "yard", factor: 50 }];
  const { rows, usedRuleIds } = buildUnitRows(units, master, rules, [{ value: "length", label: "Panjang" }]);
  const by = Object.fromEntries(rows.map((r) => [r.code, r]));
  expect(by.meter).toMatchObject({ factor: 1, source: "Satuan dasar", dimension: "Panjang" });
  expect(by.yard).toMatchObject({ factor: 0.9144, source: "Master satuan" });
  expect(by.cm).toMatchObject({ factor: 0.01, source: "Aturan konversi" });
  expect(by.roll).toMatchObject({ factor: null, source: "Per produk (kemasan)" });
  expect([...usedRuleIds]).toEqual(["r-cm"]);
});

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
import { CONFIG_GROUP_IDS } from "../settings/config/configDeepLink";
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

describe("P16-K1 — menu Pengaturan 7 kelompok", () => {
  test("Pengaturan = grup (groupId tetap settings-hub) dengan sub-judul Kebijakan per Domain", () => {
    const g = settingsGroup();
    expect(g.type).toBe("group");
    const ids = g.items.map((i) => i.id);
    expect(ids).toEqual(["settings-company", "settings-approval", "h-settings-domain", "settings-sales",
      "settings-warehouse", "settings-purchasing", "settings-finance", "settings-hr", "settings-rnd",
      "h-settings-system", "settings-masters", "settings-documents", "settings-notify", "settings-system"]);
    expect(g.items.find((i) => i.id === "h-settings-domain")).toMatchObject({ type: "heading", label: "Kebijakan per Domain" });
    expect(HUB_TABS["settings-hub"]).toBeUndefined();
    // "Semua pengaturan" tetap di menu (audit_config_wiring) — di Integrasi & Sistem.
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
    expect(Object.keys(menu("admin"))).toHaveLength(12);
    expect(menu("manager")["settings-approval"]).toContain("approval-rules");
    expect(menu("manager")["settings-system"]).toEqual(["settings-config", "settings-cfg-system", "settings-devices"]);
    expect(menu("warehouse_admin")).toEqual({ "settings-warehouse": ["settings-receiving-ocr", "grade-master"] });
    expect(menu("sales_admin")).toEqual({ "settings-sales": ["return-policies"], "settings-warehouse": ["grade-master"] });
    ["sales", "finance", "md", "designer", "driver"].forEach((r) => expect(menu(r)).toBeNull());
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
  test("23 kelompok registri masing-masing tepat di SATU layar settings-cfg-*", () => {
    // Cermin backend/config_registry.py GROUPS (uji backend test_phase3_p2_settings_groups.py membandingkan langsung).
    expect(CONFIG_GROUP_IDS).toHaveLength(23);
    const owners = CONFIG_GROUP_IDS.map((g) => [g, CONFIG_GROUP_VIEW_IDS.filter((v) => CONFIG_GROUP_VIEWS[v].groups.includes(g))]);
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
    expect(configTargetFor({ key: "commission.strategy" })).toEqual({ view: "incentive-rates", nav: "settings-sales" });
    expect(configTargetFor({ group: "makloon", key: "makloon.contract_mode" })).toEqual({ view: "settings-cfg-purchasing", nav: "settings-purchasing" });
    expect(configTargetFor({ key: "tidak_dikenal.x" })).toEqual({ view: "settings-config", nav: "settings-system" });
    expect(configDeepLinkTarget({ group: "rnd" }, "admin")).toEqual({ view: "settings-cfg-rnd", nav: "settings-rnd" });
    expect(configDeepLinkTarget({ group: "rnd" }, "md")).toEqual({ view: "settings-config", nav: "settings-system" });
    expect(configDeepLinkTarget({ key: "ai.sales_definition", group: "asisten-analitik" }, "manager"))
      .toEqual({ view: "settings-cfg-system", nav: "settings-system" });
  });
});

describe("D-03 — kunci commission.* tidak tampil ganda", () => {
  const item = (key, group, label) => ({
    key, group, label, value: 1, default: 1, type: "int", status: "active", scopes: ["global"], help: "", impact: "",
    example: "", source_layer: "code_default", source_label: "Bawaan sistem", can_edit: true,
  });
  const items = [item("commission.strategy", "harga-diskon", "Strategi komisi"), item("pricing.max_discount", "harga-diskon", "Diskon maks"),
    item("returns.photo_required", "retur", "Foto retur"), item("tax.ppn_rate", "pajak", "PPN")];
  const groups = [
    { id: "harga-diskon", label: "Harga, Diskon & Komisi", question: "?", count: 2 },
    { id: "retur", label: "Retur Penjualan", question: "?", count: 1 },
    { id: "pajak", label: "Pajak", question: "?", count: 1 },
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
    expect(q(host, "cfg-group-harga-diskon")).not.toBeNull();
    expect(q(host, "cfg-group-retur")).not.toBeNull();
    expect(q(host, "cfg-group-pajak")).toBeNull();
    expect(q(host, "cfg-card-wrap-commission.strategy")).toBeNull();
    expect(q(host, "cfg-card-wrap-pricing.max_discount")).not.toBeNull();
    expect(eff.mock.calls.every(([p]) => p.group !== "pajak")).toBe(true);
  });
});

describe("D-04 — Aturan Persetujuan: manajer membaca, satu jalan nonaktif", () => {
  test("tanpa settings.manage: daftar tampil baca-saja (tanpa Buat/Ubah/Nonaktifkan)", async () => {
    mockGet.mockResolvedValue({ data: [{ id: "r1", doc_type: "sales_order", min_amount: 0, max_amount: 1000, required_role: "manager", sort: 1, active: true }] });
    const { host } = await mount(<ApprovalRulesSettings currentUser={{ role: "manager", permissions: { settings: ["view"] } }} />);
    expect(q(host, "rule-row-r1")).not.toBeNull();
    expect(q(host, "approval-rules-readonly")).not.toBeNull();
    expect(q(host, "create-rule-btn")).toBeNull();
    expect(q(host, "delete-rule-r1")).toBeNull();
  });

  test("dengan settings.manage: tombol Nonaktifkan berlabel, form tanpa centang Aktif", async () => {
    mockGet.mockResolvedValue({ data: [{ id: "r1", doc_type: "sales_order", min_amount: 0, max_amount: 1000, required_role: "manager", sort: 1, active: true }] });
    const { host } = await mount(<ApprovalRulesSettings currentUser={{ role: "admin", permissions: { settings: ["view", "manage"] } }} />);
    expect(q(host, "delete-rule-r1").textContent).toContain("Nonaktifkan");
    await act(async () => { q(host, "create-rule-btn").click(); });
    expect(q(host, "rule-form-modal")).not.toBeNull();
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

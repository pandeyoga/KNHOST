// MN-T1 — dua pembungkus ber-chip (Titipan & Saldo Kredit, Kas Kecil), CRM tinggal tiga sub-tab, keputusan kredit
// mengikuti izin (docs/blueprint/unit/MN-T1.md). Layar lama yang dibungkus diganti tiruan: isinya tidak diubah unit ini
// dan memanggil API sendiri. Padanan komponen untuk uji jalan U17 (alias → chip yang benar).
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../finance/AdvanceReportView", () => () => <div data-testid="layar-advance-report" />);
jest.mock("../finance/StoreCreditView", () => () => <div data-testid="layar-store-credit" />);
jest.mock("../pettycash/CashAdvancesView", () => () => <div data-testid="layar-cash-advances" />);
jest.mock("../pettycash/SettlementsView", () => () => <div data-testid="layar-settlements" />);
jest.mock("../pettycash/ReimbursePayablesView", () => () => <div data-testid="layar-reimburse-payables" />);
jest.mock("../crm/CustomerList", () => () => <div data-testid="layar-customers" />);
jest.mock("../crm/LeadsPipeline", () => () => null);
jest.mock("../crm/OmnichannelInteractions", () => () => null);
jest.mock("../crm/CollectionWorklist", () => () => null);
jest.mock("../crm/SalesForceDashboard", () => () => null);
jest.mock("../crm/IncentiveSchemeEditor", () => () => null);

import CustomerCreditView from "../finance/CustomerCreditView";
import PettyCashView from "../pettycash/PettyCashView";
import CrmView from "../crm/CrmView";
import CreditOverridesPanel from "../crm/CreditOverridesPanel";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import { registerDynamicRoles, setAccessContext } from "../../config/roles";
import builtin from "../../config/__tests__/fixtures/access_builtin_fixture.json";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  for (let i = 0; i < 4; i += 1) await act(async () => {});
  roots.push(root);
  return host;
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = ""; setAccessContext(null); registerDynamicRoles([]); mockGet.mockReset();
});
const user = (role) => ({ role, permissions: builtin.permissions[role] || {} });
const chips = (host, tid) => [...host.querySelectorAll(`[data-testid="${tid}"] button`)].map((b) => b.textContent);
const aktif = (host, tid) => host.querySelector(`[data-testid="${tid}"] button[aria-pressed="true"]`)?.textContent;
const ada = (host, tid) => !!host.querySelector(`[data-testid="${tid}"]`);

describe("Titipan & Saldo Kredit (customer-credit)", () => {
  test("dua chip; bawaan Titipan pelanggan; layar lama dirender utuh", async () => {
    const host = await mount(<CustomerCreditView currentUser={user("finance")} selectedEntity="ent_ksc" />);
    expect(chips(host, "customer-credit-bagian")).toEqual(["Titipan pelanggan", "Saldo kredit"]);
    expect(aktif(host, "customer-credit-bagian")).toBe("Titipan pelanggan");
    expect(ada(host, "layar-advance-report")).toBe(true);
    await act(async () => { host.querySelector('[data-testid="customer-credit-bagian-saldo"]').click(); });
    expect(ada(host, "layar-store-credit")).toBe(true);
    expect(ada(host, "layar-advance-report")).toBe(false);
  });
  test("U17 padanan — preset alias `store-credit` {bagian: saldo} membuka chip Saldo kredit", async () => {
    const host = await mount(
      <ViewPresetProvider preset={{ view: "customer-credit", bagian: "saldo", nonce: 1 }}>
        <CustomerCreditView currentUser={user("admin")} selectedEntity="ent_ksc" />
      </ViewPresetProvider>);
    expect(aktif(host, "customer-credit-bagian")).toBe("Saldo kredit");
    expect(ada(host, "layar-store-credit")).toBe(true);
  });
  test("chip mengikuti izin endpoint layar lamanya; tanpa izin keduanya → pesan, bukan layar 403", async () => {
    const hanyaKwitansi = await mount(<CustomerCreditView currentUser={{ role: "x", permissions: { ar_receipt: ["view"] } }} />);
    expect(chips(hanyaKwitansi, "customer-credit-bagian")).toEqual(["Saldo kredit"]);
    const kosong = await mount(<CustomerCreditView currentUser={{ role: "x", permissions: {} }} />);
    expect(ada(kosong, "customer-credit-no-access")).toBe(true);
  });
  test("hidden_views peran kustom atas id lama (advance-report) menyembunyikan chipnya", async () => {
    registerDynamicRoles([{ id: "cr_uji_titipan", label: "uji", custom: true, base_role: "", nav: { add: ["customer-credit"], remove: [] } }]);
    setAccessContext({ role: "cr_uji_titipan", permissions: { accounting: ["view"], ar_receipt: ["view"] }, view_resources: {},
      hidden_views: ["advance-report"] });
    const host = await mount(<CustomerCreditView currentUser={{ role: "cr_uji_titipan", permissions: { accounting: ["view"], ar_receipt: ["view"] } }} />);
    expect(chips(host, "customer-credit-bagian")).toEqual(["Saldo kredit"]);
  });
});

describe("Kas Kecil (petty-cash)", () => {
  test("admin & finance: tiga chip (Hutang reimburse butuh accounting.view)", async () => {
    for (const role of ["admin", "finance"]) {
      const host = await mount(<PettyCashView currentUser={user(role)} selectedEntity="ent_ksc" entities={[]} />);
      expect(chips(host, "petty-cash-bagian")).toEqual(["Pengajuan dana", "Pertanggungjawaban", "Hutang reimburse"]);
      expect(aktif(host, "petty-cash-bagian")).toBe("Pengajuan dana");
      expect(ada(host, "layar-cash-advances")).toBe(true);
    }
  });
  test("sales (tanpa accounting.view): dua chip; preset `reimburse` jatuh ke chip pertama", async () => {
    const host = await mount(
      <ViewPresetProvider preset={{ view: "petty-cash", bagian: "reimburse", nonce: 1 }}>
        <PettyCashView currentUser={user("sales")} selectedEntity="ent_ksc" entities={[]} />
      </ViewPresetProvider>);
    expect(chips(host, "petty-cash-bagian")).toEqual(["Pengajuan dana", "Pertanggungjawaban"]);
    expect(aktif(host, "petty-cash-bagian")).toBe("Pengajuan dana");
    expect(ada(host, "layar-reimburse-payables")).toBe(false);
  });
  test("U17 padanan — preset alias `settlements` membuka Pertanggungjawaban; chip lain berpindah layar", async () => {
    const host = await mount(
      <ViewPresetProvider preset={{ view: "petty-cash", bagian: "pertanggungjawaban", nonce: 2 }}>
        <PettyCashView currentUser={user("admin")} selectedEntity="ent_ksc" entities={[]} />
      </ViewPresetProvider>);
    expect(aktif(host, "petty-cash-bagian")).toBe("Pertanggungjawaban");
    expect(ada(host, "layar-settlements")).toBe(true);
    await act(async () => { host.querySelector('[data-testid="petty-cash-bagian-reimburse"]').click(); });
    expect(ada(host, "layar-reimburse-payables")).toBe(true);
  });
});

describe("CRM & Pelanggan — tinggal tiga sub-tab", () => {
  test("Pelanggan · Prospek · Interaksi; sub-tab keuangan/insentif sudah pindah ke Piutang dan SDM", async () => {
    const host = await mount(<CrmView currentUser={user("admin")} selectedEntity="ent_ksc" />);
    const tabs = [...host.querySelectorAll('[data-testid^="crm-tab-"]')].map((b) => b.getAttribute("data-testid"));
    expect(tabs).toEqual(["crm-tab-customers", "crm-tab-leads", "crm-tab-interactions"]);
    expect([...host.querySelectorAll('[data-testid^="crm-tab-"]')].map((b) => b.textContent.trim()))
      .toEqual(["Pelanggan", "Prospek (Lead)", "Interaksi"]);
  });
});

describe("Kredit & Plafon (credit-overrides) — memutus hanya dengan credit_override.approve", () => {
  const baris = [{ id: "co1", customer_name: "PT Uji", reason: "lewat batas", amount: 1000, requested_by: "Sales",
    created_at: "2026-11-01T00:00:00Z", status: "pending" }];
  test.each([["manager", true], ["finance", false]])("%s: tombol Setujui/Tolak = %s", async (role, boleh) => {
    mockGet.mockResolvedValue({ data: baris });
    const host = await mount(<CreditOverridesPanel currentUser={user(role)} />);
    expect(ada(host, "override-row-co1")).toBe(true);
    expect(ada(host, "override-approve-co1")).toBe(boleh);
    expect(ada(host, "override-reject-co1")).toBe(boleh);
  });
});

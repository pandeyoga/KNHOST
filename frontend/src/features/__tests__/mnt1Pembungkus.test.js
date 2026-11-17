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
// MN-T2 — dua pembungkus ber-chip (Titipan & Saldo Kredit, Kas Kecil) diganti SATU layar masing-masing; ujinya
// pindah ke `mnt2LayarKeuangan.test.js` (U1, U2, padanan U16/U17). Di sini tinggal CRM dan Kredit & Plafon.
jest.mock("../crm/CustomerList", () => () => <div data-testid="layar-customers" />);
jest.mock("../crm/LeadsPipeline", () => () => null);
jest.mock("../crm/OmnichannelInteractions", () => () => null);
jest.mock("../crm/CollectionWorklist", () => () => null);

import CrmView from "../crm/CrmView";
import CreditOverridesPanel from "../crm/CreditOverridesPanel";
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
const ada = (host, tid) => !!host.querySelector(`[data-testid="${tid}"]`);

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
  // K-FIN-01 (pemilik 17 Nov 2026 malam) — Finance kini memegang `credit_override.approve` (setara Manajer); peran
  // pembaca tanpa hak memutus = Admin Sales.
  test.each([["manager", true], ["finance", true], ["sales_admin", false]])("%s: tombol Setujui/Tolak = %s", async (role, boleh) => {
    mockGet.mockResolvedValue({ data: baris });
    const host = await mount(<CreditOverridesPanel currentUser={user(role)} />);
    expect(ada(host, "override-row-co1")).toBe(true);
    expect(ada(host, "override-approve-co1")).toBe(boleh);
    expect(ada(host, "override-reject-co1")).toBe(boleh);
  });
});

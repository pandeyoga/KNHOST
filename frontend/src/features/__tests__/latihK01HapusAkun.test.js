// Pelatihan Keuangan 18 Nov (K01 Bagan Akun) — tombol hapus akun.
// Temuan uji jalan: (1) di bagan satu PT ikon hapus tampil juga untuk akun warisan Template Global (akun baku → 400;
// akun template bukan baku → terhapus dari SEMUA PT); (2) ikon hapus langsung menghapus tanpa konfirmasi.
// Kini: bagan PT → hanya baris "khusus PT"; Template Global → hanya akun bukan baku; selalu konfirmasi dulu.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ChartOfAccounts from "../finance/ChartOfAccounts";

const mockGet = jest.fn();
const mockDelete = jest.fn(() => Promise.resolve({ data: { ok: true } }));
const mockConfirm = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: (...a) => mockDelete(...a), request: (cfg) => (cfg.method === "delete" ? mockDelete(cfg.url, cfg) : Promise.resolve({ data: {} })),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../utils/moneyRequest", () => ({
  moneyDelete: (url, key, cfg) => mockDelete(url, cfg),
  moneyPatch: () => Promise.resolve({ data: {} }),
  moneyPost: () => Promise.resolve({ data: {} }),
}));
jest.mock("../../services/confirmService", () => ({ askConfirm: (...a) => mockConfirm(...a) }));
jest.mock("../../components/KNSelect", () => {
  const Pilih = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Pilih, KNSelect: Pilih };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function flush() { for (let i = 0; i < 5; i += 1) { await act(async () => {}); } }   // eslint-disable-line no-await-in-loop
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
const MANAGER = { id: "u_mgr", role: "manager", permissions: { accounting: ["view", "create", "void", "manage"] } };
const AKUN = [
  { code: "1-1100", name: "Kas Besar / Bank", type: "asset", normal_balance: "debit", is_postable: true, is_active: true,
    system: true, entity_id: null },
  { code: "6-4800", name: "Beban Template Lama", type: "expense", normal_balance: "debit", is_postable: true,
    is_active: true, system: false, entity_id: null },
  { code: "6-4950", name: "Beban Latihan", type: "expense", normal_balance: "debit", is_postable: true, is_active: true,
    system: false, entity_id: "ent_ksc" },
];
const ENT = [{ id: "ent_ksc", short_name: "Sukacita" }];
beforeEach(() => { mockGet.mockImplementation(() => Promise.resolve({ data: AKUN })); });
afterEach(() => { mockGet.mockReset(); mockDelete.mockClear(); mockConfirm.mockReset(); document.body.innerHTML = ""; });

describe("Bagan Akun — tombol hapus mengikuti lingkup", () => {
  test("bagan satu PT: hanya baris khusus PT yang bisa dihapus", async () => {
    const host = await mount(<ChartOfAccounts entities={ENT} currentUser={MANAGER} selectedEntity="ent_ksc" />);
    expect(q(host, "coa-row-6-4950")).toBeTruthy();
    expect(!!q(host, "coa-delete-6-4950")).toBe(true);
    expect(!!q(host, "coa-delete-1-1100")).toBe(false);   // akun baku warisan template
    expect(!!q(host, "coa-delete-6-4800")).toBe(false);   // akun template bukan baku: hapus = kena semua PT
  });

  test("Template Global: akun bukan baku bisa dihapus, akun baku tidak", async () => {
    mockGet.mockImplementation(() => Promise.resolve({ data: AKUN.filter((a) => !a.entity_id) }));
    const host = await mount(<ChartOfAccounts entities={ENT} currentUser={MANAGER} selectedEntity="all" />);
    expect(!!q(host, "coa-delete-6-4800")).toBe(true);
    expect(!!q(host, "coa-delete-1-1100")).toBe(false);
  });

  test("hapus minta konfirmasi; batal = tidak ada permintaan hapus; setuju = hapus akun PT itu saja", async () => {
    const host = await mount(<ChartOfAccounts entities={ENT} currentUser={MANAGER} selectedEntity="ent_ksc" />);
    mockConfirm.mockResolvedValueOnce(false);
    await act(async () => { q(host, "coa-delete-6-4950").click(); });
    await flush();
    expect(mockConfirm).toHaveBeenCalledTimes(1);
    const tanya = mockConfirm.mock.calls[0][0];
    expect(tanya.title).toContain("6-4950");
    expect(tanya.message).toContain("PT lain tidak terpengaruh");
    expect(mockDelete).not.toHaveBeenCalled();

    mockConfirm.mockResolvedValueOnce(true);
    await act(async () => { q(host, "coa-delete-6-4950").click(); });
    await flush();
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockDelete.mock.calls[0][0]).toBe("/api/gl/accounts/6-4950");
    expect(mockDelete.mock.calls[0][1]).toEqual(expect.objectContaining({ params: { entity_id: "ent_ksc" } }));
  });
});

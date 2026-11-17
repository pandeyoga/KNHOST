// Pelatihan Keuangan 18 Nov 2026 (F06 Kredit & Plafon) — pencarian antrean: jawaban LAMA (daftar tanpa saringan yang
// lebih lambat) tidak boleh menimpa hasil pencarian yang lebih baru. Dulu kotak cari berisi "Latihan 23" sementara tabel
// menampilkan semua pelanggan (urutan tiba jawaban acak).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CreditDeskView from "../finance/CreditDeskView";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: jest.fn(), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/EntityScopeBanner", () => () => null);
jest.mock("../../components/PaginationBar", () => (p) => <div data-testid={p.testId}>{p.total}</div>);
jest.mock("../crm/CreditOverridesPanel", () => () => null);
jest.mock("../crm/CreditProfileRequestsPanel", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await act(async () => {}); };
const baris = (id, nama) => ({ kind: "izin_kredit", id, customer_id: `c_${id}`, customer_name: nama, entity_id: "ent_ksc",
  amount: 50000000, requested_by: "Ayu", age_days: 0, summary: "", blocked_reason: "" });
const FIN = { id: "u_fin", role: "finance", permissions: { credit_profile: ["view", "update"], credit_override: ["view"] } };
const ENT = [{ id: "ent_ksc", short_name: "Sukacita" }];

test("jawaban daftar tanpa saringan yang tiba TERLAMBAT tidak menimpa hasil pencarian", async () => {
  let lepasLama;
  mockGet.mockImplementation((url, cfg) => {
    if (url.endsWith("/credit-desk/summary")) return Promise.resolve({ data: { menunggu_keputusan: 3, combined: false } });
    if (!cfg?.params?.q) {          // daftar awal: lambat, baru dilepas sesudah hasil pencarian tiba
      return new Promise((res) => { lepasLama = () => res({ data: { items: [baris("cro_a", "Konveksi Maju"),
        baris("cro_b", "Latihan 23 · Toko Kain Peserta 23")], total: 2, page: 1, page_size: 25 } }); });
    }
    return Promise.resolve({ data: { items: [baris("cro_b", "Latihan 23 · Toko Kain Peserta 23")], total: 1, page: 1,
      page_size: 25 } });
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(<EntityScopeProvider selectedEntity="ent_ksc" entities={ENT}><CreditDeskView currentUser={FIN}
      selectedEntity="ent_ksc" /></EntityScopeProvider>);
  });
  await flush();
  const input = q("credit-desk-search");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "Latihan 23");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { await new Promise((r) => setTimeout(r, 400)); });   // jeda pencarian 300 ms
  await flush();
  expect(q("credit-desk-row-cro_b")).toBeTruthy();
  expect(q("credit-desk-row-cro_a")).toBeNull();
  await act(async () => { lepasLama(); });                                      // jawaban lama tiba belakangan
  await flush();
  expect(q("credit-desk-row-cro_a")).toBeNull();
  expect(q("credit-desk-row-cro_b")).toBeTruthy();
  await act(async () => { root.unmount(); });
  host.remove();
});

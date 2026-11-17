// Pelatihan Keuangan 18 Nov (A1 Pesanan sampai Uang Masuk) — temuan uji jalan layar:
//  • Pemeriksaan muat: Gudang melihat isian & tombol [Override] lalu ditolak 403 (server: izin `wms.approve`).
//  • Rincian pesanan: "Belum ada pengiriman tercatat" tampil selama daftar surat jalan masih dimuat.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { LoadingCheckPanel } from "../wms/LoadingCheckPanel";
import { setAccessContext } from "../../config/roles";

jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: () => Promise.resolve({ data: {} }), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(el); });
  for (let i = 0; i < 4; i += 1) { await act(async () => {}); }   // eslint-disable-line no-await-in-loop
}
afterEach(() => { document.body.innerHTML = ""; setAccessContext(null); });

test.each([
  ["Gudang (wms view/update)", { role: "warehouse", permissions: { wms: ["view", "update"] } }, false],
  ["Kepala Gudang (wms approve)", { role: "warehouse_admin", permissions: { wms: ["view", "update", "approve"] } }, true],
  ["Admin", { role: "admin" }, true],
])("%s → isian override tampil %s", async (_n, user, tampil) => {
  setAccessContext(user);
  await mount(<LoadingCheckPanel orderId="so_1" soNumber="KSC/SO-00110" warehouseId="wh_1" />);
  expect(!!q("lc-override")).toBe(tampil);
  expect(!!q("lc-override-reason")).toBe(tampil);
  expect(!!q("lc-override-hint")).toBe(!tampil);
});

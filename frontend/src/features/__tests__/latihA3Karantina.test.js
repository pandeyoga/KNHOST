// Pelatihan Keuangan 18 Nov (A3 Retur) — panel karantina retur dibuka Sales; dulu selalu memanggil `GET /suppliers`
// (izin `supplier.view`, tidak dimiliki Sales) → 403 di setiap muat. Kini daftar supplier hanya dimuat bila berizin.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ReturnQuarantinePanel from "../sales/ReturnQuarantinePanel";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../hooks/useDomainEnums", () => ({
  __esModule: true,
  default: () => ({ options: () => [], labelOf: (k, v) => v || "—", fieldRules: () => ({ required: [] }), fieldLabels: {}, loading: false }),
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => { mockGet.mockImplementation(() => Promise.resolve({ data: [] })); });   // CRA: resetMocks per uji
afterEach(() => { document.body.innerHTML = ""; setAccessContext(null); });

test.each([
  ["Sales (tanpa supplier.view)", { role: "sales", permissions: { sales_return: ["view", "create"] } }, false],
  ["Admin Sales (supplier.view)", { role: "sales_admin", permissions: { supplier: ["view"] } }, true],
])("%s → daftar supplier dimuat: %s", async (_n, user, dimuat) => {
  setAccessContext(user);
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(<ReturnQuarantinePanel ret={{ id: "sret_1" }} onReleased={() => {}} />); });
  for (let i = 0; i < 4; i += 1) { await act(async () => {}); }   // eslint-disable-line no-await-in-loop
  expect(mockGet.mock.calls.some(([url]) => String(url).endsWith("/suppliers"))).toBe(dimuat);
});

// K-SDM-01 (pemilik 17 Nov 2026) — Finance membuka SDM › Karyawan: tanpa izin akun pengguna (`user.view`) layar tidak
// lagi meminta daftar akun (`GET /api/users` → 403 di setiap muat); tombol Tambah/Ubah mengikuti izin `hr.create/update`,
// tanpa tombol Tandai keluar (`hr.delete` tetap Manajer).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import EmployeesView from "../hr/EmployeesView";
import builtin from "../../config/__tests__/fixtures/access_builtin_fixture.json";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../../components/EntityBadge", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const EMP = [{ id: "emp_1", code: "EMP-00001", name: "Andi Pratama", status: "active", entity_id: "ent_ksc", base_salary: 7500000 }];
async function mount(user) {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url === "/api/hr/employees" ? EMP : [] }));
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(<EmployeesView currentUser={user} selectedEntity="ent_ksc" />); });
  for (let i = 0; i < 6; i += 1) await act(async () => {});
  return host;
}
afterEach(() => { mockGet.mockReset(); document.body.innerHTML = ""; });

test("Finance: tanpa GET /api/users; Tambah & Ubah tampil, Tandai keluar tidak", async () => {
  const host = await mount({ role: "finance", permissions: builtin.permissions.finance });
  expect(mockGet.mock.calls.map((c) => c[0])).not.toContain("/api/users");
  expect(host.querySelector('[data-testid="create-employee-button"]')).toBeTruthy();
  expect(host.querySelector('[data-testid="edit-employee-emp_1"]')).toBeTruthy();
  expect(host.querySelector('[data-testid="deactivate-employee-emp_1"]')).toBeNull();
});

test("Manajer (berizin akun pengguna) tetap memuat daftar akun", async () => {
  await mount({ role: "manager", permissions: { ...builtin.permissions.manager, user: ["view"] } });
  expect(mockGet.mock.calls.map((c) => c[0])).toContain("/api/users");
});

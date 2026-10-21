// Keputusan owner 2026-10-21 — akses semua badan usaha (lintas PT) diatur per peran di editor "Peran & Hak Akses":
// sakelar per peran (bawaan & kustom), tercantum di konfirmasi simpan, dikirim sebagai `cross_entity`; Admin dikunci.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import RoleEditorDrawer from "../settings/entities/RoleEditorDrawer";

jest.mock("../settings/entities/entityApi", () => ({
  createAccessRole: jest.fn(), patchAccessRole: jest.fn(), deleteAccessRole: jest.fn(), resetAccessRole: jest.fn(),
  errText: (e, d) => d,
}));
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../settings/entities/RoleMenuPreview", () => () => null);
jest.mock("../settings/entities/RoleAccountsList", () => () => null);
jest.mock("../settings/entities/RoleDangerDialog", () => () => null);
jest.mock("../settings/entities/RoleNotifPreview", () => () => null);
jest.mock("../settings/entities/RoleAdvancedPanel", () => () => null);
jest.mock("../settings/entities/RoleNavTree", () => ({ __esModule: true, default: () => null, titleOf: (x) => x }));
const api = require("../settings/entities/entityApi");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const FINANCE = { id: "finance", label: "Finance", custom: false, locked: false, users: 2, permissions: {}, hidden_views: [],
  cross_entity: false, cross_entity_default: false, version: "v1", turn_alerts: [] };
async function mount(role) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<RoleEditorDrawer role={role} roles={[role]} modules={[]} labels={{}} onClose={() => {}} onSaved={() => {}} />); });
  return { host, root };
}

test("sakelar lintas PT: berubah → muncul di konfirmasi & dikirim sebagai cross_entity", async () => {
  api.patchAccessRole.mockResolvedValue({ ...FINANCE, cross_entity: true, label: "Finance", users: 2 });
  const { host, root } = await mount(FINANCE);
  expect(q(host, "role-editor-cross-entity-default").textContent).toContain("mati");
  expect(q(host, "role-editor-save").disabled).toBe(true);                 // belum ada perubahan
  await act(async () => { q(host, "role-editor-cross-entity-toggle").click(); });
  expect(q(host, "role-editor-save").disabled).toBe(false);
  await act(async () => { q(host, "role-editor-save").click(); });
  expect(q(host, "role-editor-confirm-cross").textContent).toMatch(/mati → aktif/);
  await act(async () => { q(host, "role-editor-confirm-save").click(); });
  expect(api.patchAccessRole).toHaveBeenCalledWith("finance", expect.objectContaining({ cross_entity: true, expected_version: "v1" }));
  await act(async () => { root.unmount(); });
});

test("tanpa perubahan sakelar → cross_entity tidak dikirim; Admin dikunci", async () => {
  api.patchAccessRole.mockClear();
  const { host, root } = await mount({ ...FINANCE, id: "admin", label: "Admin", locked: true, cross_entity: true, cross_entity_default: true });
  expect(q(host, "role-editor-cross-entity-toggle").disabled).toBe(true);
  expect(q(host, "role-editor-cross-entity-toggle").checked).toBe(true);
  await act(async () => { root.unmount(); });
});
